"""WISEP's benchmark: how fast it decides, what its store costs on this machine, how much it saves in simulation, and
(with --live) that two identical OpenAlex asks reach the network once. Run on every operating system by
.github/workflows/wisep.yml; prints lines for people and writes wisep-bench.json for the run's artifacts.

    python tools/wisep_bench.py [--live] [--out wisep-bench.json]
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src")]

from mygeeky import wisep  # noqa: E402


def decisions(n: int = 100_000) -> float:
    """Microseconds per decision."""
    t = time.perf_counter()
    for i in range(n):
        wisep.decide(float(i % 300), ("search", "entity", "citations", "static")[i % 4], i % 7, float(i % 500),
                     (i % 10) / 10, i % 1500, 1500, (i % 100) / 100)
    return (time.perf_counter() - t) / n * 1e6


def store_cost(n: int = 2000, size: int = 5000) -> dict[str, float]:
    """Writing n answers of `size` bytes to a real file: time per write, the file's size, and that the cap holds."""
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "wisep.sqlite"
        st = wisep.reset(path)
        body = b"x" * size
        now = time.time()
        t = time.perf_counter()
        for i in range(n):
            st.put(f"k{i}", "openalex", "search", f"https://api.openalex.org/works?i={i}", body + str(i).encode(), "p", now)
        per_write_ms = (time.perf_counter() - t) / n * 1000
        t = time.perf_counter()
        for i in range(n):
            st.get(f"k{i}")
        per_read_ms = (time.perf_counter() - t) / n * 1000
        st.db.close()
        files = [p for p in Path(d).iterdir() if p.name.startswith("wisep.sqlite")]
        return {"write_ms": round(per_write_ms, 3), "read_ms": round(per_read_ms, 3),
                "mb_on_disk": round(sum(p.stat().st_size for p in files) / 1e6, 2), "answers": n}


def simulation(seeds=(1, 2, 3, 4, 5)) -> dict[str, float]:
    rows = [(wisep.simulate("timers", s), wisep.simulate("wisep", s)) for s in seeds]
    calls_t = sum(t["calls"] for t, _ in rows) / len(rows)
    calls_w = sum(w["calls"] for _, w in rows) / len(rows)
    return {"calls_timers": calls_t, "calls_wisep": calls_w, "saved_share": round(1 - calls_w / calls_t, 3),
            "stale_timers": round(sum(t["stale_share"] for t, _ in rows) / len(rows), 3),
            "stale_wisep": round(sum(w["stale_share"] for _, w in rows) / len(rows), 3)}


def live() -> dict[str, float]:
    """Two identical asks: the first reaches OpenAlex, the second is answered from the store."""
    wisep.reset(":memory:")
    url, params = "https://api.openalex.org/works", {"filter": "doi:10.1038/s41586-020-2308-7", "select": "id,title"}
    t = time.perf_counter()
    first = wisep.get(url, params, page="world:papers")
    net_ms = (time.perf_counter() - t) * 1000
    t = time.perf_counter()
    second = wisep.get(url, params, page="world:papers")
    cache_ms = (time.perf_counter() - t) * 1000
    s = wisep.stats()
    return {"status": first.status_code, "network_ms": round(net_ms, 1), "cache_ms": round(cache_ms, 2),
            "asked": s["asked"], "saved": s["saved"], "same_answer": first.content == second.content}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--out", default="wisep-bench.json")
    a = ap.parse_args()
    out = {"os": platform.platform(), "python": platform.python_version(), "cpu_count": os.cpu_count(),
           "decision_us": round(decisions(), 2), "store": store_cost(), "simulation": simulation()}
    if a.live:
        out["live"] = live()
    print(f"{out['os']} · Python {out['python']}")
    print(f"  a decision takes {out['decision_us']} µs")
    s = out["store"]
    print(f"  the store: {s['write_ms']} ms a write, {s['read_ms']} ms a read, {s['mb_on_disk']} MB for {s['answers']} answers")
    m = out["simulation"]
    print(f"  simulation: {m['calls_wisep']:.0f} calls against {m['calls_timers']:.0f} with fixed timers "
          f"({m['saved_share']:.0%} saved); stale views {m['stale_wisep']:.1%} against {m['stale_timers']:.1%}")
    if a.live:
        lv = out["live"]
        print(f"  live: OpenAlex answered {lv['status']} in {lv['network_ms']} ms; the same ask again: {lv['cache_ms']} ms "
              f"from the store ({lv['asked']} asked, {lv['saved']} saved)")
    Path(a.out).write_text(json.dumps(out, indent=1))
    ok = m["calls_wisep"] < 0.5 * m["calls_timers"] and m["stale_wisep"] <= m["stale_timers"] + 0.05 \
        and out["decision_us"] < 200 and s["write_ms"] < 50 and (not a.live or (out["live"]["asked"] == 1 and out["live"]["saved"] == 1))
    print("  OK" if ok else "  NOT OK: see the numbers above")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
