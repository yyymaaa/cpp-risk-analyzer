from datetime import datetime

from tests.conftest import commit, write
from cpp_risk_analyzer.graph.cochange import CoChangeIndex


def test_cochange_counts():
    """Co-change index counts how often two files change in the same commit.
    Req: FR2
    Expected: a.h changed 3 times, together with b.cc twice; b.cc is a.h's top partner
    """
    co = CoChangeIndex([["a.h", "b.cc"], ["a.h", "b.cc", "c.cc"], ["a.h"], ["c.cc"]])
    assert co.n("a.h") == 3
    assert co.together("a.h", "b.cc") == 2
    assert co.partners("a.h").most_common(1)[0] == ("b.cc", 2)


def test_cochange_mined_from_git(tiny_repo, tmp_path):
    """Co-change history is mined from real Git commits, skipping oversized commits.
    Req: FR2
    Expected: core.h and util.h counted together in 2 commits; a 41-file commit is ignored
    """
    now = datetime.now()
    for i in range(2):
        write(tiny_repo, "include/lib/core.h", f"// {i}\n")
        write(tiny_repo, "include/lib/util.h", f"// {i}\n")
        commit(tiny_repo, f"change {i}", now)
    for i in range(41):                                  # bulk commit (e.g. reformatting)
        write(tiny_repo, f"gen/f{i}.h", "x")
    write(tiny_repo, "include/lib/core.h", "// bulk\n")
    commit(tiny_repo, "bulk", now)
    co = CoChangeIndex.mine(tiny_repo, tmp_path / "cache")
    assert co.together("include/lib/core.h", "include/lib/util.h") == 2
    assert co.n("gen/f0.h") == 0
