"""Shared helpers: config, week windows, raw-data index."""
import json, os, glob, datetime as dt

SKILL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def load_cfg(path):
    with open(path) as f:
        return json.load(f)

def save_cfg(cfg, path):
    with open(path, "w") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=1)

def d(s):
    return dt.date.fromisoformat(s)

def last_complete_sunday(run_date):
    """Sunday of the most recent Mon-Sun week that ended before run_date."""
    r = d(run_date) if isinstance(run_date, str) else run_date
    return r - dt.timedelta(days=(r.weekday() + 1) % 7 or 7)

def weeks(cfg, run_date):
    """Shown weeks (oldest first) plus baseline W0 and the partial week after.
    Returns list of (label, start_iso, end_iso, kind) with kind in base/show/next."""
    end = last_complete_sunday(run_date)
    start = d(cfg["start_week"])
    mons = []
    m = start
    while m + dt.timedelta(days=6) <= end:
        mons.append(m)
        m += dt.timedelta(days=7)
    mons = mons[-cfg.get("max_weeks", 8):]
    out = []
    w0 = mons[0] - dt.timedelta(days=7)
    out.append(("W0", w0.isoformat(), (w0 + dt.timedelta(days=6)).isoformat(), "base"))
    n0 = (mons[0] - start).days // 7 + 1
    for i, m in enumerate(mons):
        e = m + dt.timedelta(days=6)
        lab = f"第{n0+i}周 {m.month}/{m.day}-{e.month}/{e.day}"
        out.append((lab, m.isoformat(), e.isoformat(), "show"))
    nx = end + dt.timedelta(days=1)
    last = d(run_date) - dt.timedelta(days=1)
    out.append(("NEXT", nx.isoformat(), max(nx, last).isoformat(), "next"))
    return out

def pull_range(cfg, run_date):
    w = weeks(cfg, run_date)
    return w[0][1], (d(run_date) - dt.timedelta(days=1)).isoformat()

def raw_index(dirs):
    """Map (asin, tool) -> raw json path across oc_pull output dirs; later dirs win.
    Skips files without data.trends (duplicates / errors)."""
    idx = {}
    for o in dirs:
        ip = os.path.join(o, "raw", "index.json")
        if not os.path.exists(ip):
            continue
        for e in json.load(open(ip)):
            a = e.get("args", {}).get("asin")
            if e.get("error") or not a:
                continue
            f = os.path.join(o, "raw", e["file"])
            try:
                if json.load(open(f)).get("data", {}).get("trends") is None:
                    continue
            except Exception:
                continue
            idx[(a, e["tool"])] = f
    return idx

def run_dirs(run):
    """All oc_pull output dirs under a run folder (any subfolder holding raw/index.json)."""
    return sorted({os.path.dirname(os.path.dirname(p)) for p in glob.glob(os.path.join(run, "**", "raw", "index.json"), recursive=True)})

def trends(path):
    return {r["date"]: r for r in json.load(open(path)).get("data", {}).get("trends", [])}

def all_items(cfg):
    """tracked + risers + siblings with name/brand/keyword/rank."""
    out = {}
    for t in cfg.get("tracked", []):
        out[t["asin"]] = dict(t, role="tracked")
        for s in t.get("siblings", []):
            out.setdefault(s["asin"], dict(s, brand=t["brand"], role="sibling"))
    for r in cfg.get("risers", []):
        out[r["asin"]] = dict(r, role="riser")
    return out
