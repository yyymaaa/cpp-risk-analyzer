"""Generate the test record (test, requirement, expected, actual, corrective action) as Markdown.

Usage:
    python -m pytest --junitxml=initial.xml      # first run, before fixes
    ...fix the failures...
    python -m pytest --junitxml=final.xml
    python tests/make_test_record.py initial.xml final.xml > tests/TEST_RECORD.md

Each test's docstring provides the description, "Req:" and "Expected:" lines (see conftest.py).
Corrective actions for tests that failed in the initial run are listed in CORRECTIVE_ACTIONS below.
"""
import ast
import sys
import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent

CORRECTIVE_ACTIONS = {
    "test_validator_counts_and_cycles":
        "Defect: `GraphValidator.run_structural_checks` reported `edge_count` using `number_of_nodes()`. "
        "Fixed to `number_of_edges()` in graph/validator.py.",
    "test_unterminated_include_ignored":
        "Defect: the parser raised `UnboundLocalError` on `#include <` without a closing `>` (and would reuse a "
        "stale path from an earlier line). Rewrote extraction in core/parser.py with a single regular expression "
        "that requires a matching closing delimiter.",
    "test_space_after_hash_extracted":
        "Defect: valid includes such as `#  include \"a.h\"` and `#include<b.h>` were silently missed. Fixed by the "
        "same regular expression (allows whitespace after `#` and none before the delimiter). Effect on real "
        "repositories: +29 include edges in RocksDB, +42 in Catch2, none in LevelDB or Abseil.",
    "test_no_model_does_not_hang":
        "Defect found by the Windows CI run (passed on Linux and macOS): on Windows, input redirected from the NUL "
        "device reports isatty() = True, so the tool showed the 'Build one now?' prompt, received no answer and exited "
        "with a bare 'Aborted.'. Fixed in cpp_risk_analyzer/cli.py: on Windows the tool now asks the OS whether stdin is "
        "a real console (GetConsoleMode), and an unanswered prompt now prints the `risk build` guidance. Regression tests "
        "added (test_no_prompt_without_console, test_unanswered_prompt_gives_guidance).",
    "test_purge_removes_overlapping_labels":
        "Test defect, not a code defect: the test expected a row whose 90-day label window ends exactly on the "
        "first test date to be purged. That window does not overlap the test labels (which start after that "
        "date), so keeping it is correct. Corrected the test's expected result.",
}


def docstrings():
    """Map test name -> (file, description, requirement, expected)."""
    out = {}
    for f in sorted(TESTS_DIR.glob("test_*.py")):
        for node in ast.walk(ast.parse(f.read_text())):
            if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
                doc = ast.get_docstring(node) or ""
                lines = [l.strip() for l in doc.splitlines()]
                desc, req, exp, cur = [], "", [], None
                for l in lines:
                    if l.startswith("Req:"):
                        req, cur = l[4:].strip(), None
                    elif l.startswith("Expected:"):
                        exp, cur = [l[9:].strip()], exp
                        cur = exp
                    elif cur is exp and l:
                        exp.append(l)
                    elif not req and l:
                        desc.append(l)
                out[node.name] = (f.stem, " ".join(desc), req, " ".join(exp))
    return out


def results(xml_path):
    """Map test name -> 'Pass' or 'Fail: <short reason>'."""
    res = {}
    for case in ET.parse(xml_path).getroot().iter("testcase"):
        fail = case.find("failure") if case.find("failure") is not None else case.find("error")
        if fail is None:
            res[case.get("name")] = "Pass"
        else:
            msg = (fail.get("message") or "").splitlines()[0][:110]
            res[case.get("name")] = f"Fail: {msg}".replace("|", "\\|")
    return res


def main(initial_xml, final_xml):
    docs, first, final = docstrings(), results(initial_xml), results(final_xml)
    # Only count tests that still exist (renamed or replaced tests drop out of the record)
    first = {k: v for k, v in first.items() if k in docs}
    final = {k: v for k, v in final.items() if k in docs}
    n_fail_first = sum(v != "Pass" for v in first.values())
    n_pass_final = sum(v == "Pass" for v in final.values())
    print("# Test Record\n")
    print(f"Generated {date.today().isoformat()} by `tests/make_test_record.py` from two pytest runs "
          f"(before and after corrective actions).\n")
    print(f"- Tests: **{len(final)}**  ·  initial run: **{len(first) - n_fail_first} passed, {n_fail_first} failed**"
          f"  ·  final run: **{n_pass_final} passed, {len(final) - n_pass_final} failed**")
    print("- Requirement IDs refer to Chapter 4 (FR = functional, NFR = non-functional requirement).")
    print("- Final run recorded on Linux. GitHub Actions also runs the full suite on Windows and macOS on every push; "
          "see the Actions tab for those runs.")
    print("- Run them yourself: `pip install -e \".[test]\"` then `python -m pytest` "
          "(add `-m \"not slow\"` to skip the end-to-end tests).\n")
    print("| ID | Module | Test | Requirement | Expected result | Initial result | Corrective action | Final result |")
    print("|---|---|---|---|---|---|---|---|")
    for i, (name, (mod, desc, req, exp)) in enumerate(sorted(docs.items(), key=lambda kv: (kv[1][0], kv[0])), 1):
        action = CORRECTIVE_ACTIONS.get(name, "None needed" if first.get(name) == "Pass" else "")
        print(f"| T{i:02d} | {mod.removeprefix('test_')} | {desc} | {req} | {exp} | "
              f"{first.get(name, 'Not run')} | {action} | {final.get(name, 'Not run')} |")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
