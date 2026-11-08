from core.parser import extract_includes


def _parse(tmp_path, text):
    f = tmp_path / "f.cc"
    f.write_text(text)
    return extract_includes(f)


def test_quoted_include_extracted(tmp_path):
    """Quoted include is extracted with its path, delimiter and line number.
    Req: FR1
    Expected: one directive: path "a/b.h", delimiter '"', line 2
    """
    inc = _parse(tmp_path, '// header\n#include "a/b.h"\n')
    assert [(i.path, i.delimiter, i.line_number) for i in inc] == [("a/b.h", '"', 2)]


def test_angle_include_extracted(tmp_path):
    """Angle-bracket include is extracted with delimiter '<'.
    Req: FR1
    Expected: one directive: path "vector", delimiter '<'
    """
    inc = _parse(tmp_path, "#include <vector>\n")
    assert [(i.path, i.delimiter) for i in inc] == [("vector", "<")]


def test_multiple_includes_in_order(tmp_path):
    """All includes in a file are returned in source order.
    Req: FR1
    Expected: paths ["x.h", "map", "y/z.hpp"] with line numbers 1, 2, 4
    """
    inc = _parse(tmp_path, '#include "x.h"\n#include <map>\nint a;\n#include "y/z.hpp"\n')
    assert [(i.path, i.line_number) for i in inc] == [("x.h", 1), ("map", 2), ("y/z.hpp", 4)]


def test_indented_include_extracted(tmp_path):
    """Indented include (e.g. inside #ifdef) is still extracted.
    Req: FR1
    Expected: one directive "a.h"
    """
    inc = _parse(tmp_path, '#ifdef X\n    #include "a.h"\n#endif\n')
    assert [i.path for i in inc] == ["a.h"]


def test_space_after_hash_extracted(tmp_path):
    """Valid C++ spacing such as `# include "a.h"` and `#include<b.h>` is extracted.
    Req: FR1
    Expected: two directives "a.h" and "b.h"
    """
    inc = _parse(tmp_path, '#  include "a.h"\n#include<b.h>\n')
    assert [i.path for i in inc] == ["a.h", "b.h"]


def test_commented_include_ignored(tmp_path):
    """Commented-out includes are not treated as dependencies.
    Req: FR1
    Expected: no directives
    """
    assert _parse(tmp_path, '// #include "a.h"\n/* #include "b.h" */\n') == []


def test_unterminated_include_ignored(tmp_path):
    """A malformed include with no closing delimiter is skipped without crashing.
    Req: FR1, robustness
    Expected: only the valid include "ok.h" is returned; no exception
    """
    inc = _parse(tmp_path, '#include <broken\n#include "also_broken\n#include "ok.h"\n')
    assert [i.path for i in inc] == ["ok.h"]


def test_non_utf8_file_does_not_crash(tmp_path):
    """Files with invalid UTF-8 bytes are parsed without crashing.
    Req: NFR1, robustness
    Expected: the include "a.h" is returned
    """
    f = tmp_path / "latin1.cc"
    f.write_bytes(b'// caf\xe9\n#include "a.h"\n')
    assert [i.path for i in extract_includes(f)] == ["a.h"]
