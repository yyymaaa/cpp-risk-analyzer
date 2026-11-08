import re
from collections import defaultdict
from dataclasses import dataclass, field

import networkx as nx
import pandas as pd
from rich.panel import Panel
from rich.text import Text

HOP_PRIOR = {1: 0.50, 2: 0.25, 3: 0.10}   # hand-set weights by include distance (heuristic, not measured probabilities)
DEFAULT_PRIOR = 0.04
REVIEW_AT, WATCH_AT = 55, 30               # score cutoffs: tune on your repos
MIN_REVIEW, MAX_REVIEW = 5, 12             # review list is never empty, never a wall

# Real tests: *_test.cc, test_*.cc, or anything under test/ or tests/ directories.
TEST_RE = re.compile(r"(^|/)(tests?|testing)/|_tests?\.(cc|cpp|cxx)$|(^|/)test_[^/]*\.(cc|cpp|cxx)$", re.I)
# Supporting tooling: not tests, not product code.
TOOL_RE = re.compile(r"(^|/)(tools?|test_util)/|bench|stress|mock|_test_util|testutil|testharness", re.I)

PINK, PURPLE, LILAC, RED = "#ff70a6", "#c77dff", "#b28dff", "#ff0a54"
GRADE_COLOR = {"CRITICAL": RED, "HIGH": PINK, "MODERATE": PURPLE, "LOW": LILAC}


def classify(path: str) -> str:
    if TEST_RE.search(path):
        return "test"
    if TOOL_RE.search(path):
        return "tool"
    return "prod"


def bar(frac: float, width: int = 12) -> str:
    n = max(0, min(width, round(frac * width)))
    return "█" * n + "░" * (width - n)


@dataclass
class Hit:
    file: str
    dist: int
    likelihood: float
    blast_pct: float
    score: float
    kind: str                       # prod | test | tool
    tier: str = "IGNORE"            # REVIEW | WATCH | RUN | TOOL | IGNORE
    why: list[str] = field(default_factory=list)

    @property
    def is_test(self):
        return self.kind == "test"


@dataclass
class Report:
    target: str
    grade: str
    target_pct: float
    hits: list[Hit]
    hidden: list[tuple[str, int, float]]
    n_target_commits: int
    n_strong: int
    mode: str
    trust: dict | None

    @property
    def reachable(self): return len(self.hits)
    def tier(self, t): return [h for h in self.hits if h.tier == t]


def compute_report(an, target: str) -> Report:
    g, co = an.graph, an.cochange
    paths = nx.single_target_shortest_path(g, target)   # edges: dependent -> dependency
    paths.pop(target, None)

    if an.has_model:
        blast_pct = an.current_state["predicted_blast_radius"].rank(pct=True)
        commit_pct = an.current_state["historical_commit_count_365d"].rank(pct=True)
    else:
        blast_pct = pd.Series({k: v.get("pagerank", 0.0) for k, v in an.metrics.items()}).rank(pct=True)
        commit_pct = None

    n_t = co.n(target)
    hits = []
    for dep, path in paths.items():
        dist = len(path) - 1
        k = co.together(target, dep)
        conf = k / n_t if n_t >= 5 else 0.0              # P(dep changes | target changes)
        like = 1 - (1 - HOP_PRIOR.get(dist, DEFAULT_PRIOR)) * (1 - conf)
        bp = float(blast_pct.get(dep, 0.5))
        score = 100 * like * (0.4 + 0.6 * bp)

        why = []
        if k:
            why.append(f"changed with {target.split('/')[-1]} in {k}/{n_t} past commits ({conf:.0%})")
        why.append("includes it directly" if dist == 1
                   else f"{dist} hops away via {path[1].split('/')[-1]}")
        if an.has_model and dep in an.current_state.index:
            row = an.current_state.loc[dep]
            c, cp = row["historical_commit_count_365d"], float(commit_pct.get(dep, 0))
            if c >= 5 and cp >= 0.90:
                why.append(f"{int(c)} commits last year (busier than {cp:.0%} of files)")
            if row["fan_in"] > an.percentiles_90["fan_in"]:
                why.append(f"{int(row['fan_in'])} files depend on it in turn (top 10%)")

        hits.append(Hit(dep, dist, like, bp, score, classify(dep), why=why))
    hits.sort(key=lambda h: h.score, reverse=True)

    # Tiering: only prod code competes for REVIEW; tests are RUN; tooling is TOOL.
    n_strong = n_rev = seen_prod = 0
    for h in hits:
        if h.kind == "test":
            h.tier = "RUN" if h.score >= WATCH_AT else "IGNORE"
        elif h.kind == "tool":
            h.tier = "TOOL" if h.score >= WATCH_AT else "IGNORE"
        else:
            strong = h.score >= REVIEW_AT
            n_strong += strong
            if (strong or seen_prod < MIN_REVIEW) and n_rev < MAX_REVIEW:
                h.tier, n_rev = "REVIEW", n_rev + 1
            elif h.score >= WATCH_AT:
                h.tier = "WATCH"
            seen_prod += 1

    # Hidden coupling: moves with the target in git, but no include relationship either way.
    known = set(paths) | nx.descendants(g, target) | {target}
    hidden = [(f, c, c / n_t) for f, c in co.partners(target).most_common(60)
              if f in g.nodes and f not in known and n_t >= 5 and c / n_t >= 0.15][:8]

    tp = float(blast_pct.get(target, 0.5))
    levels = ["LOW", "MODERATE", "HIGH", "CRITICAL"]
    s = 3 if n_strong >= 12 else 2 if n_strong >= 6 else 1 if n_strong >= 2 else 0
    h = 3 if tp >= 0.95 else 2 if tp >= 0.80 else 1 if tp >= 0.50 else 0
    grade = levels[max(s, min(h, s + 1))]   # structure sets the grade; history can add one level
    mode = "ML blast-radius model + git co-change history" if an.has_model else "structural fallback + git history"
    return Report(target, grade, tp, hits, hidden, n_t, n_strong, mode, getattr(an, "trust", None))


def trust_line(t: dict | None, has_model: bool) -> str | None:
    if not has_model:
        return None
    if not t:
        return "model trust: unavailable (run `risk build` to record accuracy)"
    r2 = t["r2"]
    label = "reliable" if r2 >= 0.6 else "directional" if r2 >= 0.3 else "weak, treat as a hint"
    s = (f"model trust: R² {r2:.2f} ({label}) · typical error ±{t['rmse']:.1f} files "
         f"vs ±{t['baseline_rmse']:.1f} for a naive guess")
    if t.get("best_baseline_rmse") is not None:
        s += f", ±{t['best_baseline_rmse']:.1f} for the best simple rule"
    if t.get("low_activity_test"):
        s += " · ⚠ test period had little activity"
    if t.get("test_from"):
        s += f" · tested on {t['test_from']} → {t['test_to']}"
    return s


def render(r: Report, console, show_all: bool = False):
    col = GRADE_COLOR[r.grade]
    review, watch = r.tier("REVIEW"), r.tier("WATCH")
    tests, tools = r.tier("RUN"), r.tier("TOOL")
    likely = len(review) + len(watch) + len(tests) + len(tools)

    head = Text()
    head.append(f"{r.target}\n", style="bold white")
    head.append(f"{bar(r.target_pct, 20)}  ", style=col)
    head.append(r.grade, style=f"bold {col}")
    if "ML" in r.mode:
        head.append(f"   predicted to change alongside more files than {r.target_pct:.0%} of the repo\n\n", style=LILAC)
    else:
        head.append(f"   more central (PageRank) than {r.target_pct:.0%} of the repo\n\n", style=LILAC)
    if r.reachable:
        head.append(f"{r.reachable} files can reach this change.  ", style="white")
        head.append(f"Only {len(review)} need your eyes.", style=f"bold {PINK}")
    else:
        head.append("Nothing #includes this file, so it can't break other files at compile time.\n", style="white")
        head.append("Its risk is behavioral: see what moves with it in git below.", style=f"bold {PINK}")
    head.append(f"\n{r.mode} · this file changed in {r.n_target_commits} commits in the last 2 years", style="dim")
    tl = trust_line(r.trust, "ML" in r.mode)
    if tl:
        head.append(f"\n{tl}", style="dim")
    console.print(Panel(head, border_style=LILAC, padding=(1, 2)))

    if r.reachable:

        console.print(f"[bold {PURPLE}]THE FUNNEL[/]")
        for label, n, style in [("reachable via #include", r.reachable, LILAC),
                                ("likely affected", likely, PURPLE),
                                ("must review", len(review), PINK)]:
            console.print(f"  {n:>5}  [{style}]{bar(n / max(r.reachable, 1), 30)}[/] {label}")

        if r.hidden:
            console.print(f"\n[bold {PURPLE}]HIDDEN COUPLING[/] [dim]moves with this file in git, but no #include links them[/]")
            for f, c, conf in r.hidden:
                console.print(f"  [{PINK}]{bar(conf, 10)}[/] {conf:>4.0%}  {f}  [dim]({c}/{r.n_target_commits} commits)[/]")

        shown = sorted(review + (watch if show_all else []), key=lambda h: h.score, reverse=True)
        limit = len(shown) if show_all else 7
        console.print(f"\n[bold {PURPLE}]REVIEW THESE[/] [dim]product code, ranked by risk score (include distance, git co-change, predicted blast radius)[/]")
        for i, h in enumerate(shown[:limit], 1):
            tag = "" if h.tier == "REVIEW" else "  [dim](watch)[/]"
            console.print(f"  [bold white]{i}. {h.file}[/]  [{PINK}]{bar(h.score / 100, 10)} {h.score:.0f}[/]{tag}")
            for j, w in enumerate(h.why):
                console.print(f"     [{LILAC}]{'└' if j == len(h.why) - 1 else '├'}─ {w}[/]")
        hidden_n = len(review) + len(watch) - limit if not show_all else 0
        if len(shown) > limit or (not show_all and watch):
            console.print(f"  [dim]+ {max(len(shown) - limit, 0) + len(watch)} lower-priority files to watch (use --all)[/]")

        if tests:
            total_tests = sum(h.kind == "test" for h in r.hits)
            console.print(f"\n[bold {PURPLE}]RUN THESE TESTS[/] [dim]{len(tests)} of {total_tests} reachable tests are worth running[/]")
            cap = len(tests) if show_all else 8
            for h in tests[:cap]:
                console.print(f"  [{LILAC}]▸[/] {h.file}")
            if len(tests) > cap:
                console.print(f"  [dim]+ {len(tests) - cap} more (use --all)[/]")

        if tools:
            names = ", ".join(h.file.split("/")[-1] for h in tools[: len(tools) if show_all else 3])
            more = "" if show_all or len(tools) <= 3 else f" +{len(tools) - 3} more"
            console.print(f"\n[bold {PURPLE}]ALSO TOUCHED[/] [dim]{len(tools)} tools/benchmarks/stress harnesses: {names}{more}[/]")

        heat = defaultdict(float)
        for h in r.hits:
            if h.tier != "IGNORE":
                heat[h.file.split("/")[0]] += h.score
        if heat:
            console.print(f"\n[bold {PURPLE}]WHERE IT HURTS[/]")
            top = max(heat.values())
            for d, v in sorted(heat.items(), key=lambda kv: -kv[1])[:6]:
                console.print(f"  {d:<22} [{PINK}]{bar(v / top, 24)}[/]")
        console.print()

    if not r.reachable:
        console.print()
        return