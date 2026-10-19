# 배경지도 원본(basemap_raw.json)을 대시보드용으로 줄임: 작은 면 제거 + 더글러스-푀커 단순화
import json, re, sys
src = json.load(open("basemap_raw.json")); L = src["layers"]
# 층별: (단순화 허용오차[10m 단위], 최소 면적[(10m)^2], 최소 길이[10m])
CFG = {"fo": (12, 150000, 0), "ur": (4, 6000, 0), "wt": (3, 1500, 0), "rv": (2.5, 0, 80), "cn": (3, 0, 150),
       "mw": (3, 0, 0), "tr": (3.5, 0, 0), "pr": (4, 0, 50), "sc": (5, 0, 100), "rw": (3, 0, 60)}
def parse(d):
    out = []
    for m in re.finditer(r"M(-?\d+) (-?\d+)((?:l-?\d+ -?\d+)*)(z?)", d):
        x, y = int(m.group(1)), int(m.group(2)); pts = [(x, y)]
        nums = list(map(int, re.findall(r"-?\d+", m.group(3))))
        for i in range(0, len(nums), 2): x += nums[i]; y += nums[i + 1]; pts.append((x, y))
        out.append((pts, m.group(4) == "z"))
    return out
def dp(pts, tol):
    if len(pts) < 3: return pts
    keep = [False] * len(pts); keep[0] = keep[-1] = True; st = [(0, len(pts) - 1)]
    while st:
        a, b = st.pop(); ax, ay = pts[a]; bx, by = pts[b]; dx, dy = bx - ax, by - ay; L2 = dx * dx + dy * dy or 1e-9; best, bi = -1, -1
        for i in range(a + 1, b):
            px, py = pts[i]; t = max(0, min(1, ((px - ax) * dx + (py - ay) * dy) / L2)); ex, ey = ax + t * dx - px, ay + t * dy - py; d2 = ex * ex + ey * ey
            if d2 > best: best, bi = d2, i
        if bi > 0 and best > tol * tol: keep[bi] = True; st += [(a, bi), (bi, b)]
    return [p for p, k in zip(pts, keep) if k]
def area(p): return abs(sum(p[i][0] * p[i + 1][1] - p[i + 1][0] * p[i][1] for i in range(len(p) - 1)) + p[-1][0] * p[0][1] - p[0][0] * p[-1][1]) / 2
def length(p): return sum(((p[i + 1][0] - p[i][0]) ** 2 + (p[i + 1][1] - p[i][1]) ** 2) ** .5 for i in range(len(p) - 1))
def enc(pts, z):
    s = "M%d %d" % pts[0]; px, py = pts[0]
    for x, y in pts[1:]:
        if (x, y) == (px, py): continue
        s += "l%d %d" % (x - px, y - py); px, py = x, y
    return s + ("z" if z else "")
res, stat = {}, {}
for k, d in L.items():
    tol, amin, lmin = CFG.get(k, (3, 0, 0)); parts = []
    for pts, z in parse(d):
        if z and amin and area(pts) < amin: continue
        if not z and lmin and length(pts) < lmin: continue
        q = dp(pts, tol)
        if z and len(q) < 4: continue
        if len(q) >= 2: parts.append(enc(q, z))
    res[k] = "".join(parts); stat[k] = (len(d) // 1000, len(res[k]) // 1000)
from datetime import date
json.dump({"origin": src["origin"], "layers": res, "attrib": src["attrib"], "asof": "2026-10"}, open("basemap.json", "w"), separators=(",", ":"))
print(stat, sum(len(v) for v in res.values()) // 1000, "KB")
