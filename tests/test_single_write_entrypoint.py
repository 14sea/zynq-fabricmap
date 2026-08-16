"""There is no second device-write entrypoint — checked, not claimed.

The reviewer's boundary was that the production path must ALWAYS go through
`board_uboot_transmit(session)`: one verified `BoardSession`, `authorise_write("uboot")`
before every write, and no other way to reach the fabric. Saying so in a docstring is worth
nothing — the whole point is that a *future* edit must not be able to add a second door
quietly. So this file reads the source of every module under `scripts/` and `host/` and
pins the inventory of sites that can reach the wire.

Five independent facts, each of which a second entrypoint would have to break:

  1. the carrier's AXI window addresses are named in exactly ONE module;
  2. `WRITE_CAPABILITY` — the token `execute_transaction` demands — is held at exactly ONE
     site, and that site is `BoardSession.write_sequence`;
  3. `session.write_sequence(...)` is called from exactly ONE site;
  4. `run_candidate(...)` — the gate→guard→wire path — is called from exactly ONE site, and
     `board_uboot_transmit` is used at exactly ONE site, and they are the same function;
  5. that function, `run_candidate_on_board`, has no parameter through which a caller could
     supply a transmit: no `transmit`, no `*args`, no `**kwargs`, no callable default.

Tests are excluded from the inventory on purpose. Injection has to stay reachable from a
test — that is how the wiring is exercised without a board — and a test cannot write to a
device it does not have. What must not exist is a *production* path with a choice in it.
"""

from __future__ import annotations

import ast
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIRS = (REPO_ROOT / "scripts", REPO_ROOT / "host")

# The one module allowed to name the window and hold the capability.
TRANSPORT = "board_uboot_axi.py"
SESSION = "gate_board_identity.py"
EXEC = "board_carrier_exec.py"
POSTFAULT_CAPTURE = "board_claimb_postfault_capture.py"


def source_files() -> list[Path]:
    files: list[Path] = []
    for directory in SOURCE_DIRS:
        if directory.is_dir():
            files.extend(
                path for path in sorted(directory.rglob("*.py"))
                if "__pycache__" not in path.parts
            )
    return files


def sites(predicate) -> list[tuple[str, str]]:
    """Every (file, enclosing qualified function) where `predicate(node)` holds.

    Module level counts as `<module>`; a name used there is as reachable as one in a
    function, and an inventory that only looked inside functions would miss the simplest
    possible bypass — a module-level alias.
    """
    found: list[tuple[str, str]] = []

    def walk(node, scope: list[str], filename: str) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                if predicate(child):
                    found.append((filename, ".".join(scope) or "<module>"))
                walk(child, scope + [child.name], filename)
            else:
                if predicate(child):
                    found.append((filename, ".".join(scope) or "<module>"))
                walk(child, scope, filename)

    for path in source_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        walk(tree, [], path.name)
    return found


def attribute_call(name: str):
    def predicate(node) -> bool:
        return (isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == name)
    return predicate


def plain_call(name: str):
    def predicate(node) -> bool:
        return (isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == name)
    return predicate


def any_reference(name: str):
    def predicate(node) -> bool:
        return ((isinstance(node, ast.Name) and node.id == name)
                or (isinstance(node, ast.Attribute) and node.attr == name))
    return predicate


class WindowIsNamedOnce(unittest.TestCase):
    def test_only_the_transport_names_the_carrier_axi_window(self) -> None:
        """A second writer would have to say where it is writing."""
        naming = []
        for path in source_files():
            text = path.read_text(encoding="utf-8").lower()
            if "0x43c0" in text or "43c00000" in text:
                naming.append(path.name)
        self.assertEqual(
            naming, [TRANSPORT],
            f"the carrier AXI window is named in {naming}; it belongs in {TRANSPORT} alone")

    def test_the_transport_offers_no_command_line(self) -> None:
        """`board_uboot_axi` must not be runnable. A CLI is an entrypoint by definition."""
        tree = ast.parse((REPO_ROOT / "scripts" / TRANSPORT).read_text(encoding="utf-8"))
        names = {node.name for node in tree.body
                 if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
        self.assertNotIn("main", names)
        self.assertNotIn(
            "__main__", (REPO_ROOT / "scripts" / TRANSPORT).read_text(encoding="utf-8"))


class ThereIsOneScorerArm(unittest.TestCase):
    """The no-op still never arms; the known-answer chain has exactly one reviewed door."""

    def test_the_arm_bits_are_used_only_by_the_transport_arm_function(self) -> None:
        for constant in ("CTRL_ARM", "CTRL_MODE_HOLDOUT"):
            used = [site for site in sites(any_reference(constant))]
            self.assertEqual(
                used, [(TRANSPORT, "<module>"), (TRANSPORT, "arm_scorer")],
                f"{constant} has an unreviewed use at {used}")

    def test_the_score_capability_is_held_once(self) -> None:
        found = [site for site in sites(any_reference("SCORE_CAPABILITY"))
                 if site[0] != TRANSPORT]
        self.assertEqual(found, [(SESSION, "BoardSession.score_last_transaction")])

    def test_the_arm_function_is_called_at_one_site(self) -> None:
        self.assertEqual(sites(attribute_call("arm_scorer")),
                         [(SESSION, "BoardSession.score_last_transaction")])

    def test_the_session_score_path_is_called_from_one_production_site(self) -> None:
        self.assertEqual(sites(attribute_call("score_last_transaction")),
                         [("board_claimb_known_answer.py", "_score")])

    def test_the_reviewed_round_has_one_production_caller(self) -> None:
        self.assertEqual(sites(plain_call("run_known_answer_round")),
                         [("board_claimb_known_answer.py", "main")])

    def test_the_postfault_capture_module_cannot_name_the_evaluation_path(self) -> None:
        source = (REPO_ROOT / "scripts" / POSTFAULT_CAPTURE).read_text(encoding="utf-8")
        forbidden = ("_score", "score_last_transaction", "arm_scorer",
                     "CTRL_ARM", "CTRL_MODE_HOLDOUT", "run_known_answer_round")
        self.assertEqual([name for name in forbidden if name in source], [])
        self.assertEqual(sites(plain_call("run_postfault_capture")),
                         [(POSTFAULT_CAPTURE, "main")])


class TheCapabilityIsHeldOnce(unittest.TestCase):
    def test_write_capability_is_referenced_at_one_site(self) -> None:
        found = [site for site in sites(any_reference("WRITE_CAPABILITY"))
                 if site[0] != TRANSPORT]
        self.assertEqual(found, [(SESSION, "BoardSession.write_sequence")])

    def test_execute_transaction_is_called_at_one_site(self) -> None:
        found = sites(attribute_call("execute_transaction"))
        self.assertEqual(found, [(SESSION, "BoardSession.write_sequence")])

    def test_write_sequence_is_called_at_one_site(self) -> None:
        found = sites(attribute_call("write_sequence"))
        self.assertEqual(found, [(EXEC, "board_uboot_transmit.transmit")])


class ThereIsOneProductionPath(unittest.TestCase):
    def test_run_candidate_is_called_at_one_site(self) -> None:
        found = [site for site in sites(plain_call("run_candidate"))]
        self.assertEqual(found, [(EXEC, "run_candidate_on_board")])

    def test_board_uboot_transmit_is_used_at_one_site(self) -> None:
        found = [site for site in sites(plain_call("board_uboot_transmit"))]
        self.assertEqual(found, [(EXEC, "run_candidate_on_board")])

    def test_the_production_entrypoint_cannot_be_handed_a_transmit(self) -> None:
        tree = ast.parse((REPO_ROOT / "scripts" / EXEC).read_text(encoding="utf-8"))
        function = next(node for node in tree.body
                        if isinstance(node, ast.FunctionDef)
                        and node.name == "run_candidate_on_board")
        args = function.args
        self.assertEqual([a.arg for a in args.args], ["payload", "authority", "session"])
        self.assertEqual(args.posonlyargs, [])
        self.assertEqual(args.kwonlyargs, [])
        self.assertIsNone(args.vararg, "*args could carry a transmit")
        self.assertIsNone(args.kwarg, "**kwargs could carry a transmit")
        self.assertEqual(args.defaults, [], "a default could be a callable")

    def test_the_production_entrypoint_builds_its_own_transmit(self) -> None:
        """Not just "calls both" — the transmit passed to `run_candidate` must be the one
        `board_uboot_transmit` returns, in that call, from that session."""
        tree = ast.parse((REPO_ROOT / "scripts" / EXEC).read_text(encoding="utf-8"))
        function = next(node for node in tree.body
                        if isinstance(node, ast.FunctionDef)
                        and node.name == "run_candidate_on_board")
        calls = [node for node in ast.walk(function)
                 if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                 and node.func.id == "run_candidate"]
        self.assertEqual(len(calls), 1)
        third = calls[0].args[2]
        self.assertIsInstance(third, ast.Call)
        self.assertEqual(third.func.id, "board_uboot_transmit")
        self.assertEqual([a.id for a in third.args], ["session"])


if __name__ == "__main__":
    unittest.main()
