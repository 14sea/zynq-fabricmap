#!/usr/bin/env python3
"""Run the unchanged B2 application main under the existing fake BSP, off board.

Only the harness is adapted: install a checksummed page and add a scripted IDENTACK.
No firmware source, image, manifest, pin or board is modified.
"""
import json
from pathlib import Path
import subprocess
import tempfile

R = Path(__file__).resolve().parents[3]
FW = R / "firmware/b2"
H = R / "tb/b2/hostapp"
source = (H / "hostapp.c").read_text()
source = source.replace("static char last_rec_outcome[64];", "static char last_rec_outcome[64];\nstatic int strict_identity;")
needle = '    if (!strcmp(type, "SIGNREQ")) {'
assert source.count(needle) == 1
source = source.replace(needle, r'''
    if (!strcmp(type, "IDENT")) {
        if (!strict_identity ||
            (strstr(frame_json, "\"pairs_total\":9") &&
             strstr(frame_json, "\"pair_first\":4") &&
             strstr(frame_json, "\"pair_count\":4")))
            reply("IDENTACK", 0, "{\"seq\":0}");
    } else if (!strcmp(type, "SIGNREQ")) {''')
start = source.index("int main(int argc, char **argv)")
source = source[:start] + r'''
int main(int argc, char **argv)
{
    uint32_t page[P3_PAGE_WORDS] = {0};
    uint32_t flags = 2u | (8u << 16) | (4u << 20) | (3u << 24);
    const char *scenario = argc > 1 ? argv[1] : "strict";
    strict_identity = !strcmp(scenario, "strict");
    if (!strcmp(scenario, "reserved")) flags |= 1u << 28;
    if (!strcmp(scenario, "outside")) flags = 2u | (8u << 16) | (8u << 20) | (3u << 24);
    page[0] = P3_PAGE_MAGIC; page[1] = P3_PAGE_LAYOUT;
    page[2] = 0xa13f38b5u; page[3] = 0x3355fd4cu;
    page[4] = 0x1cac3145u; page[5] = 0x244727f8u;
    page[6] = 1u; page[7] = 0xf54b0ae9u;
    page[16] = (uint32_t)fake_nonce; page[17] = (uint32_t)(fake_nonce >> 32);
    page[18] = (1u << 8) | (1u << 11);
    page[19] = 716169644u; page[20] = 600u; page[21] = flags; page[22] = 50000000u;
    for (int i = 0; i < P3_PAGE_WORDS - 1; i++) page[P3_PAGE_WORDS - 1] ^= page[i];
    for (int i = 0; i < P3_PAGE_WORDS; i++) mem_wr(P3_PAGE_ADDR + 4u * (uint32_t)i, page[i]);
    script.ack_rec = 1; script.ack_term = 1; script.signref_at_seq = 1;
    int rc = b2_app_main();
    print_result(scenario);
    return rc;
}
'''
results = {}
with tempfile.TemporaryDirectory(prefix="b2-startup-review-") as tmp:
    tmp = Path(tmp)
    cfile = tmp / "startup.c"
    cfile.write_text(source)
    exe = tmp / "startup"
    units = ["p3_derive.c", "b2_search.c", "b2_orch.c", "b2_wire.c", "p3_rectx.c", "p3_pull.c"]
    subprocess.run(["cc", "-std=gnu11", "-O1", "-g", "-Wall", "-Wno-unused-function",
                    "-fsanitize=undefined", "-fno-sanitize-recover=all",
                    f"-I{FW}", f"-I{H / 'hostbsp'}", str(cfile),
                    *[str(FW / unit) for unit in units], "-o", str(exe)], check=True)
    for scenario in ("strict", "ack_all", "reserved", "outside"):
        run = subprocess.run([str(exe), scenario], capture_output=True, text=True, check=True, timeout=30)
        frames = [json.loads(line) for line in run.stdout.splitlines() if line.startswith("{")]
        result = next(json.loads(line[7:]) for line in run.stdout.splitlines() if line.startswith("RESULT "))
        results[scenario] = {"frames": frames, "result": result, "stderr": run.stderr}
print(json.dumps(results, indent=2))
