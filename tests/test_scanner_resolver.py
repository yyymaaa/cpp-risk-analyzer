from cpp_risk_analyzer.core.parser import IncludeDirective
from cpp_risk_analyzer.core.resolver import resolve_include
from cpp_risk_analyzer.core.scanner import scan_repository


def test_scanner_finds_cpp_files_only(tiny_repo):
    """Scanner returns C/C++ sources and headers, sorted, and nothing else.
    Req: FR1
    Expected: exactly the 7 .h/.cc files of the fixture; README.md and CMakeLists.txt excluded
    """
    (tiny_repo / "README.md").write_text("x")
    (tiny_repo / "CMakeLists.txt").write_text("x")
    found = [p.relative_to(tiny_repo).as_posix() for p in scan_repository(tiny_repo)]
    assert len(found) == 7
    assert found == sorted(found)
    assert all(f.endswith((".h", ".cc")) for f in found)


def test_scanner_skips_third_party_and_build(tiny_repo):
    """Vendored and build directories are excluded from analysis.
    Req: FR1, data preparation
    Expected: files under third-party/ and build/ are not returned
    """
    (tiny_repo / "third-party").mkdir()
    (tiny_repo / "third-party" / "dep.h").write_text("x")
    (tiny_repo / "build").mkdir()
    (tiny_repo / "build" / "gen.h").write_text("x")
    found = [p.relative_to(tiny_repo).as_posix() for p in scan_repository(tiny_repo)]
    assert not any(f.startswith(("third-party/", "build/")) for f in found)


def test_resolve_include_dir_path(tiny_repo):
    """An include written relative to include/ resolves to the repository file.
    Req: FR1
    Expected: status "internal", target include/lib/core.h
    """
    r = resolve_include(IncludeDirective("lib/core.h", '"', 1), tiny_repo / "src/engine.cc", tiny_repo)
    assert r.status == "internal"
    assert r.target == (tiny_repo / "include/lib/core.h").resolve()


def test_resolve_relative_to_source(tiny_repo):
    """An include relative to the including file's folder resolves.
    Req: FR1
    Expected: status "internal", target include/lib/core.h
    """
    r = resolve_include(IncludeDirective("core.h", '"', 1), tiny_repo / "include/lib/util.h", tiny_repo)
    assert r.status == "internal"
    assert r.target.name == "core.h"


def test_resolve_system_header_external(tiny_repo):
    """A standard-library header is classified as external, not a repository dependency.
    Req: FR1
    Expected: status "external", no target
    """
    r = resolve_include(IncludeDirective("vector", "<", 1), tiny_repo / "src/engine.cc", tiny_repo)
    assert (r.status, r.target) == ("external", None)


def test_resolve_missing_quoted_unresolved(tiny_repo):
    """A quoted include that does not exist is reported as unresolved.
    Req: FR1
    Expected: status "unresolved", no target
    """
    r = resolve_include(IncludeDirective("nope.h", '"', 1), tiny_repo / "src/engine.cc", tiny_repo)
    assert (r.status, r.target) == ("unresolved", None)
