"""Write a tab spec to Feishu with lark-cli (no high-risk commands).
Usage: python3 write_tab.py --token SHEET_TOKEN --spec SPEC.json --images IMG_DIR [--log LOG]
Spec keys: tab, header (list of rows), rows, footer (text, merged across ncols), ncols, base_styles, styles,
  merges, images [{cell, asin}], col_sizes, row_height, footer_height, freeze, check_col (0-based col to verify).
Steps: create tab if missing -> unmerge old merges -> blank leftover old rows -> write values -> styles ->
  images -> grow clipped rows -> read back and print a short report."""
import json, subprocess, sys, os, csv, io, argparse, shutil
ap = argparse.ArgumentParser(); ap.add_argument("--token", required=True); ap.add_argument("--spec", required=True)
ap.add_argument("--images", default=""); ap.add_argument("--log", default="/dev/null")
ap.add_argument("--domain", default="amazon.com", help="Amazon domain for ASIN links, e.g. amazon.co.uk"); A = ap.parse_args()
LC = shutil.which("lark-cli") or os.path.expanduser("~/.npm-global/bin/lark-cli")
S = json.load(open(A.spec)); T = A.token; TAB = S["tab"]; NC = S["ncols"]
log = open(A.log, "a")
def run(*args, q=None, cwd=None):
    cmd = [LC, "sheets", *args, "--spreadsheet-token", T] + (["-q", q] if q else [])
    p = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd); log.write(" ".join(args[:1]) + " " + p.stdout[-400:] + p.stderr[-400:] + "\n")
    return p.stdout
def col(i):
    s = ""; i += 1
    while i: i, r = divmod(i - 1, 26); s = chr(65 + r) + s
    return s
def csvtext(rows):
    b = io.StringIO(); csv.writer(b, lineterminator="\n").writerows(rows); return b.getvalue()
LAST = col(NC - 1)
names = json.loads(run("+workbook-info", q="[.data.sheets[].sheet_name]") or "[]")
if TAB not in names:
    run("+sheet-create", "--title", TAB, "--col-count", str(max(NC, 12)), "--row-count", str(len(S["rows"]) + 60))
info = json.loads(run("+sheet-info", "--sheet-name", TAB, q=".data") or "{}")
for m in info.get("merged_cells", []):
    run("+cells-unmerge", "--sheet-name", TAB, "--range", m["range"])
used = run("+csv-get", "--sheet-name", TAB, "--range", "A1:A1000", "--include-row-prefix=false", q=".data.csv // .data.annotated_csv")
try: old_n = len([l for l in json.loads(used).splitlines()]) if used.strip().startswith('"') else len(used.splitlines())
except Exception: old_n = 0
H = len(S["header"]); body = S["header"] + S["rows"]; n = len(body); foot_row = n + 1
total = max(old_n, foot_row) + 2
blank = [[""] * NC for _ in range(total - n)]
blank[0][0] = S.get("footer", "")
open("/tmp/_wt_blank.csv", "w").write(csvtext(blank))
run("+csv-put", "--sheet-name", TAB, "--start-cell", f"A{n+1}", "--csv", "@/tmp/_wt_blank.csv")
open("/tmp/_wt_body.csv", "w").write(csvtext(body))
run("+csv-put", "--sheet-name", TAB, "--start-cell", "A1", "--csv", "@/tmp/_wt_body.csv")
BD = {"style": "solid", "weight": "thin", "color": "#D9D9D9"}
cs = [{"range": f"A1:{LAST}{H}", "background_color": "#1F4E79", "font_color": "#FFFFFF", "font_weight": "bold", "font_size": 13, "horizontal_alignment": "center", "vertical_alignment": "middle", "word_wrap": "auto-wrap", "border": BD},
      {"range": f"A{H+1}:{LAST}{n}", "font_size": 13, "font_color": "#000000", "vertical_alignment": "top", "horizontal_alignment": "left", "word_wrap": "auto-wrap", "border": BD, "background_color": "#FFFFFF", "font_weight": "normal"}]
cs += S.get("base_styles", []) + S.get("styles", [])
cs.append({"range": f"A{foot_row}:{LAST}{foot_row}", "font_color": "#7F7F7F", "font_size": 10, "vertical_alignment": "top", "horizontal_alignment": "left", "word_wrap": "auto-wrap", "background_color": "#FFFFFF", "font_weight": "normal", "border": BD})
if total > foot_row:
    cs.append({"range": f"A{foot_row+1}:{LAST}{total}", "background_color": "#FFFFFF", "font_weight": "normal", "font_size": 10, "border": {"style": "solid", "weight": "thin", "color": "#FFFFFF"}})
spec = {"name": TAB, "cell_styles": cs, "cell_merges": [{"range": f"A{foot_row}:{LAST}{foot_row}"}] + S.get("merges", []),
        "col_sizes": S.get("col_sizes", []), "row_sizes": [{"range": f"{H+1}:{n}", "size": S.get("row_height", 60)}, {"range": f"{foot_row}:{foot_row}", "size": S.get("footer_height", 150)}]}
if S.get("freeze"): spec["freeze"] = S["freeze"]
json.dump({"styles": [spec]}, open("/tmp/_wt_styles.json", "w"), ensure_ascii=False)
run("+styles-put", "--styles", "@/tmp/_wt_styles.json")
ok = fail = 0; missing = []
for im in S.get("images", []):
    f = os.path.join(A.images, im["asin"] + ".jpg")
    if not os.path.exists(f): missing.append(im["asin"]); continue
    # lark-cli only reads files under cwd, /tmp or ~/files, so run from the image folder
    out = run("+cells-set-image", "--sheet-name", TAB, "--range", im["cell"], "--image", im["asin"] + ".jpg", "--name", im["asin"] + ".jpg", cwd=A.images)
    if '"ok": true' not in out:  # one retry for transient upload errors
        out = run("+cells-set-image", "--sheet-name", TAB, "--range", im["cell"], "--image", im["asin"] + ".jpg", "--name", im["asin"] + ".jpg", cwd=A.images)
    ok, fail = (ok + 1, fail) if '"ok": true' in out else (ok, fail + 1)
# ASIN column -> clickable Amazon product links; the cell value stays the ASIN, so the value check below still works
import re
LINKC = next((j for j in range(NC) if any(j < len(h) and str(h[j]).strip().upper() == "ASIN" for h in S["header"])), None)
link_rows = []
if LINKC is not None:
    lcells = []
    for i, r in enumerate(S["rows"]):
        v = str(r[LINKC]).strip()
        if re.fullmatch(r"[A-Z0-9]{10}", v):
            lcells.append([{"rich_text": [{"type": "link", "text": v, "link": f"https://www.{A.domain}/dp/{v}"}]}]); link_rows.append(i + H + 1)
        else:
            lcells.append([{"value": r[LINKC]}])
    json.dump(lcells, open("/tmp/_wt_links.json", "w"), ensure_ascii=False)
    run("+cells-set", "--sheet-name", TAB, "--range", f"{col(LINKC)}{H+1}:{col(LINKC)}{n}", "--cells", "@/tmp/_wt_links.json")
    json.dump({"styles": [{"name": TAB, "cell_styles": [{"range": f"{col(LINKC)}{H+1}:{col(LINKC)}{n}", "font_color": "#1155CC", "font_line": "underline"}]}]}, open("/tmp/_wt_linkstyle.json", "w"), ensure_ascii=False)
    run("+styles-put", "--styles", "@/tmp/_wt_linkstyle.json")
for rnd in range(3):
    cells = json.loads(run("+cells-get", "--sheet-name", TAB, "--range", f"A1:{LAST}{foot_row}", "--include", "truncation", q=".data.ranges[0].cells") or "[]")
    tr = [i + 1 for i, r in enumerate(cells) if any(c.get("isRowTruncated") for c in r)]
    if not tr: break
    cur = {r: S.get("row_height", 60) + 80 * (rnd + 1) for r in tr}
    if foot_row in cur: cur[foot_row] = S.get("footer_height", 150) + 80 * (rnd + 1)
    run("+rows-resize", "--sheet-name", TAB, "--heights", json.dumps({str(k): v for k, v in cur.items()}))
cells = json.loads(run("+cells-get", "--sheet-name", TAB, "--range", f"A1:{LAST}{foot_row}", "--include", "value,truncation", q=".data.ranges[0].cells") or "[]")
cc = S.get("check_col", 0)
mism = [i + H + 1 for i, (r, w) in enumerate(zip(cells[H:n], S["rows"])) if str(r[cc].get("value", "")) != str(w[cc])]
noimg = [im["cell"] for im in S.get("images", []) if not any(x.get("type") == "embed-image" for x in (cells[int(im["cell"][1:]) - 1][ord(im["cell"][0]) - 65].get("rich_text") or []))]
trunc = [i + 1 for i, r in enumerate(cells) if any(c.get("isRowTruncated") for c in r)]
nolink = [f"{col(LINKC)}{rr}" for rr in link_rows if not any(x.get("type") == "link" for x in (cells[rr - 1][LINKC].get("rich_text") or []))] if LINKC is not None else []
print(json.dumps({"tab": TAB, "rows": len(S["rows"]), "footer_row": foot_row, "images_ok": ok, "images_fail": fail, "images_missing_file": missing,
                  "value_mismatch_rows": mism, "cells_without_image": noimg, "links": len(link_rows), "cells_without_link": nolink, "truncated_rows": trunc}, ensure_ascii=False))
