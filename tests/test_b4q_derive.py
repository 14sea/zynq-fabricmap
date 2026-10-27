"""B4Q — the derived C derive unit against its Python twin and against its base.

  * PARITY: firmware/b4q/b4q_derive.c (through b4q_derive_twin) and host/b4q_frames.py produce the same frames hash, stream
    digests (with the C parser's round trip), readback / cleanup command digests and nonce step over a corpus of genomes:
    0, all ones, every single bit, the loaded image's own genome, 64 seeded random genomes; a 22-bit value is refused by both.
  * VERBATIM: the functions b4q_derive.c claims unchanged from firmware/b1/p3_derive.c are byte-identical, function by
    function (the digest of each function's text); the genome codec is the one that differs.
  * GENERATED: b4q_data.h / b4q_data.json and b4q_regmap.h equal a fresh generation; the write set covers the four frames
    that hold the 21 addresses; every base frame is ECC-consistent; the derived frames differ from the base in exactly the
    whitelisted bits and the ECC words.
  * THE MANIFEST CORRECTION (before / after): the first delivery found builds/b4/b4_carrier_manifest.json naming the pre-v0.4
    bitstream digest with 22 column frames differing from the committed bitstream (the four frames holding the addresses and all
    21 values equal); the HOLD review allowed its narrow regeneration from the committed bitstream — both states are pinned, the
    old file archived in the unit directory. The base used here is the committed bitstream named by builds/b4/b4_build.json.
No skip: a missing compiler or a failed build is a failure."""
from __future__ import annotations

import hashlib
import json
import random
import re
import subprocess
import sys
import unittest
from pathlib import Path

R = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(R / "host"))
import b4q_frames as fr  # noqa: E402

FW = R / "firmware/b4q"
BUILD = R / "build/b4q_firmware"
TWIN = BUILD / "b4q_derive_twin"
VERBATIM = ("p3_sha256_init", "p3_sha256_update", "p3_sha256_final", "p3_sha256_words", "p3_hex", "p3_crc32", "p3_frame_ecc",
            "p3_frame_update_ecc", "p3_genome_to_hex", "p3_genome_bit", "p3_derive_frames", "p3_build_stream", "p3_parse_stream",
            "p3_frames_hash", "p3_build_readback_command", "p3_build_cleanup_command", "p3_nonce_step")
CHANGED = ("p3_genome_from_hex",)
_STATE: dict = {}


def setUpModule():
    p = subprocess.run(["make", "-C", str(FW), "twin"], capture_output=True, text=True)
    if p.returncode != 0 or not TWIN.is_file():
        raise AssertionError(f"the derive twin did not build (a failure, never a skip):\n{p.stdout}{p.stderr}")
    _STATE["base"] = fr.load_base()
    _STATE["wl"] = fr.whitelist()


def c_function(text: str, name: str) -> str:
    m = re.search(rf"^[a-z0-9_ \*]*\b{re.escape(name)}\(.*?^\}}\n", text, re.M | re.S)
    if not m:
        raise AssertionError(f"function {name} not found")
    return m.group(0)


def twin(genomes: list[str]) -> list[dict]:
    p = subprocess.run([str(TWIN)], input="".join(g + "\n" for g in genomes), capture_output=True, text=True, timeout=120)
    assert p.returncode == 0, p.stderr
    return [json.loads(l) for l in p.stdout.splitlines()]


class Parity(unittest.TestCase):
    def test_corpus(self):
        base, wl = _STATE["base"], _STATE["wl"]
        rng = random.Random(0x42345)
        genomes = [0, (1 << 21) - 1, base["frames"] and fr.genome_from_frames({f: base["frames"][f] for f in fr.TARGET_FARS}, wl)] + [1 << i for i in range(21)] + [rng.getrandbits(21) for _ in range(64)]
        out = twin([f"{g:08x}" for g in genomes])
        self.assertEqual(len(out), len(genomes))
        for g, o in zip(genomes, out):
            self.assertNotIn("refused", o, g)
            frames = fr.derive_frames(g, base["frames"], wl)
            self.assertEqual(o["round_trip"], f"{g:08x}")
            self.assertEqual(o["frames_hash"], fr.frames_hash(frames), g)
            self.assertEqual(fr.genome_from_frames(frames, wl), g)
            for e in range(len(fr.ENVELOPES)):
                s = fr.build_stream(e, frames, base["frames"])
                self.assertEqual(o["streams"][e]["sha256"], fr.words_sha256(s), (g, e))
                self.assertTrue(o["streams"][e]["parse_ok"], (g, e))
                self.assertEqual(int(o["streams"][e]["far_set"], 16), fr.ENVELOPES[e]["far_set"])
                parsed = fr.parse_stream(s)
                self.assertIsNotNone(parsed)
                self.assertEqual(parsed[0], fr.ENVELOPES[e]["far_set"])
                self.assertEqual(parsed[1][:4], [frames[t] for t in fr.ENVELOPES[e]["targets"]])
                self.assertEqual(parsed[1][4], base["frames"][fr.ENVELOPES[e]["flush"]])
            self.assertEqual(o["readback_cmd"], [fr.words_sha256(fr.build_readback_command(f)) for f in fr.TARGET_FARS])
            self.assertEqual(o["cleanup"], fr.words_sha256(fr.build_cleanup_command()))
            self.assertEqual(o["ecc"], [frames[f][50] & 0x1FFF for f in fr.TARGET_FARS])
            self.assertEqual(int(o["nonce_step"], 16), fr.nonce_step(0x9E3779B97F4A7C15 ^ g))

    def test_refusals_agree(self):
        out = twin(["00200000", "zz", "0000000", "000000001"])
        self.assertTrue(all(o.get("refused") for o in out), out)
        with self.assertRaises(fr.DeriveRefusal):
            fr.derive_frames(1 << 21, _STATE["base"]["frames"], _STATE["wl"])

    def test_the_parser_refuses_a_deviation(self):
        base, wl = _STATE["base"], _STATE["wl"]
        s = fr.build_stream(0, fr.derive_frames(5, base["frames"], wl), base["frames"])
        for i, v in ((8, 0), (20, fr.t1w(fr.REG_FAR, 1) + 1), (12, fr.CMD_RCRC + 1)):
            bad = list(s); bad[i] = v
            self.assertIsNone(fr.parse_stream(bad), i)
        bad = list(s); bad[21] = 0x00400a05                      # an unknown FAR set
        self.assertIsNone(fr.parse_stream(bad))


class Verbatim(unittest.TestCase):
    def test_functions_byte_identical_to_the_base(self):
        b1 = (R / "firmware/b1/p3_derive.c").read_text()
        b4 = (FW / "b4q_derive.c").read_text()
        for name in VERBATIM:
            self.assertEqual(hashlib.sha256(c_function(b1, name).encode()).hexdigest(), hashlib.sha256(c_function(b4, name).encode()).hexdigest(), name)
        for name in CHANGED:
            self.assertNotEqual(c_function(b1, name), c_function(b4, name), name)
        for absent in ("p3_base64url", "p3_parse_identity_page"):
            self.assertNotIn(absent + "(", b4)
        h = (FW / "b4q_derive.h").read_text()
        self.assertIn("#define P3_TARGET_FRAMES 8", h); self.assertIn("#define P3_ENVELOPE_COUNT 2", h); self.assertIn("#define P3_GENOME_BITS 21", h)

    def test_import_table_names_the_base_and_the_digests(self):
        imp = json.loads((FW / "IMPORT.json").read_text())
        for rel, entry in imp["files"].items():
            p = R / rel
            self.assertTrue(p.is_file(), rel)
            if rel.endswith("IMPORT.json"):
                continue                                                     # the table's own entry carries no digest of itself
            self.assertEqual(hashlib.sha256(p.read_bytes()).hexdigest(), entry["sha256"], rel)
            if entry["kind"] in ("verbatim", "derived"):
                self.assertEqual(hashlib.sha256((R / entry["base"]).read_bytes()).hexdigest(), entry["base_sha256"], rel)
                if entry["kind"] == "verbatim":
                    self.assertEqual((R / entry["base"]).read_bytes(), p.read_bytes(), rel)
                else:
                    self.assertNotEqual((R / entry["base"]).read_bytes(), p.read_bytes(), rel)
        tracked = subprocess.run(["git", "-C", str(R), "ls-files", "firmware/b4q"], capture_output=True, text=True).stdout.split()
        self.assertEqual(sorted(set(tracked) - set(imp["files"])), [], "every tracked file under firmware/b4q has an entry")


class Generated(unittest.TestCase):
    def test_headers_equal_a_fresh_generation(self):
        for script in ("host/b4q_gen_data.py", "host/b4q_gen_regmap.py"):
            p = subprocess.run([sys.executable, "-B", str(R / script), "--check"], capture_output=True, text=True)
            self.assertEqual(p.returncode, 0, p.stdout + p.stderr)

    def test_write_set_and_base(self):
        base, wl = _STATE["base"], _STATE["wl"]
        self.assertEqual(sorted({far for far, _, _ in wl}), [0x00400a00, 0x00400a01, 0x00400a1e, 0x00400a1f])
        self.assertTrue(set(far for far, _, _ in wl) <= set(fr.TARGET_FARS))
        self.assertEqual(fr.TARGET_FARS, tuple(sorted(fr.TARGET_FARS)))
        for e in fr.ENVELOPES:
            self.assertEqual(list(e["targets"]), list(range(e["far_set"], e["far_set"] + 4)))
            self.assertEqual(e["flush"], e["far_set"] + 4)
        import frame_ecc as fe
        for far, words in base["frames"].items():
            self.assertTrue(fe.frame_is_consistent(words), hex(far))
        g = 0b101
        frames = fr.derive_frames(g, base["frames"], wl)
        for far in fr.TARGET_FARS:
            diff = [(w, base["frames"][far][w] ^ frames[far][w]) for w in range(101) if base["frames"][far][w] != frames[far][w]]
            for w, x in diff:
                self.assertTrue(w == 50 or any(f == far and ww == w for f, ww, _ in wl), (hex(far), w))

    def test_the_manifest_correction_is_a_recorded_before_and_after(self):
        """The carrier manifest of record named the pre-v0.4 bitstream (the first delivery's finding 1); the HOLD review allowed a
        narrow metadata regeneration from the committed bitstream: AFTER, the manifest's file digest is the build record's and every
        column frame equals; BEFORE (the archived manifest) 22 of 36 column frames differed while the four frames holding the 21
        addresses and all 21 values were equal — both states pinned here, the old file kept as evidence."""
        base = _STATE["base"]
        rec = json.loads((FW / "b4q_data.json").read_text())
        self.assertTrue(base["manifest_file_digest_matches"]); self.assertEqual(base["manifest_column_frames_differing"], [])
        self.assertTrue(rec["carrier_manifest_file_digest_matches"]); self.assertEqual(rec["carrier_manifest_column_frames_differing"], [])
        m = json.loads((R / fr.MANIFEST_REL).read_text())
        self.assertEqual(m["bitstream_sha256"], json.loads((R / fr.BUILD_REL).read_text())["bitstream_sha256"]); self.assertEqual(m["bitstream_sha256"], base["bitstream_sha256"])
        self.assertEqual(m["natural_build_mismatches"], [])
        old = json.loads((R / "evidence/b4/unit_b4q_integration_2026_10_27/manifest_regeneration/b4_carrier_manifest_before_52f2ea56.json").read_text())
        self.assertEqual(old["bitstream_sha256"], "52f2ea56fddd6268ce6a3b5adcf9aede9d1ab953dc8d1e75b653054524178745")
        differing = sorted(k for k, v in old["target_column_frames_sha256"].items() if base["column_frames_sha256"].get(k) != v)
        self.assertEqual(len(differing), 22)
        for far in (0x00400a00, 0x00400a01, 0x00400a1e, 0x00400a1f):
            self.assertNotIn(f"{far:#010x}", differing)
        self.assertEqual({r["address"]: r["value"] for r in old["addresses"]}, {r["address"]: r["value"] for r in m["addresses"]})
        for row in m["addresses"]:
            far, w, b = row["address"].split("/")
            self.assertEqual((base["frames"][int(far, 16)][int(w)] >> int(b)) & 1, row["value"], row["address"])

if __name__ == "__main__":
    unittest.main()
