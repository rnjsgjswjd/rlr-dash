# 최신 OSM(osmium export GeoJSONSeq, WGS84) → 대시보드 배경지도 팩
#  - 전국 개요(layers): 확대 0~2단계, 지금과 같은 층 이름
#  - T1 타일(20km): 확대 3단계 — 3차로(지방도)까지 정밀선 + 터널 구분 + 작은 호수
#  - T2 타일(5km): 확대 4단계 — 동네 길(시군도·이면도로)·실개천
#  - 라벨: 도로 이름(가장 긴 구간 가운데, 도로 방향으로), IC/JC, 읍면동·리 이름
# 좌표: EPSG:5179, 대시보드 지도 단위(10m), 원점 = 시군구 경계 지도와 동일
import json, sys, math, os, re
from pyproj import Transformer
X0, Y1, U = 741111.0312999999, 2073441.1553000007, 10.0
W, H = 56791, 61983
TR = Transformer.from_crs(4326, 5179, always_xy=True)
src, out_fn, asof = sys.argv[1], sys.argv[2], (sys.argv[3] if len(sys.argv) > 3 else "")

def proj(coords):
    xs, ys = TR.transform([c[0] for c in coords], [c[1] for c in coords])
    return [((x - X0) / U, (Y1 - y) / U) for x, y in zip(xs, ys)]

def dp(pts, tol):
    if len(pts) < 3: return pts
    keep = [False] * len(pts); keep[0] = keep[-1] = True; st = [(0, len(pts) - 1)]; t2 = tol * tol
    while st:
        a, b = st.pop(); ax, ay = pts[a]; bx, by = pts[b]; dx, dy = bx - ax, by - ay; L2 = dx * dx + dy * dy or 1e-9; best, bi = -1, -1
        for i in range(a + 1, b):
            px, py = pts[i]; t = max(0, min(1, ((px - ax) * dx + (py - ay) * dy) / L2)); ex, ey = ax + t * dx - px, ay + t * dy - py; d2 = ex * ex + ey * ey
            if d2 > best: best, bi = d2, i
        if bi > 0 and best > t2: keep[bi] = True; st += [(a, bi), (bi, b)]
    return [p for p, k in zip(pts, keep) if k]

def enc(pts, z=False):
    q = [(round(x), round(y)) for x, y in pts]; s = "M%d %d" % q[0]; px, py = q[0]; n = 0
    for x, y in q[1:]:
        if (x, y) == (px, py): continue
        dx, dy = x - px, y - py; s += "l%d%s%d" % (dx, " " if dy >= 0 else "", dy); px, py = x, y; n += 1
    if n == 0: return ""
    return s + ("z" if z else "")

def area(p): return abs(sum(p[i][0] * p[i + 1][1] - p[i + 1][0] * p[i][1] for i in range(len(p) - 1))) / 2
def length(p): return sum(math.hypot(p[i + 1][0] - p[i][0], p[i + 1][1] - p[i][1]) for i in range(len(p) - 1))
def bbox(p): xs = [a[0] for a in p]; ys = [a[1] for a in p]; return min(xs), min(ys), max(xs), max(ys)

RD = {"motorway": "mw", "motorway_link": "mw", "trunk": "tr", "trunk_link": "tr", "primary": "pr", "primary_link": "pr", "secondary": "sc", "secondary_link": "sc",
      "tertiary": "te", "tertiary_link": "te", "unclassified": "mi", "residential": "mi", "living_street": "mi"}
# 개요층 (기존 bm_thin 기준): (허용오차, 최소면적, 최소길이)
OV = {"fo": (12, 150000, 0), "ur": (4, 6000, 0), "wt": (3, 1500, 0), "rv": (2.5, 0, 80), "cn": (3, 0, 150),
      "mw": (3, 0, 0), "tr": (3.5, 0, 0), "pr": (4, 0, 50), "sc": (5, 0, 100), "rw": (3, 0, 60)}
T1S, T2S = 2000, 500
ov, t1, t2, lb1, lb2 = {}, {}, {}, {}, {}
stat = {}
MARG = 0.3  # 화면 쪽에서 타일 크기의 30% 여유를 두고 불러오므로, 그 안에 들어오면 한 타일에만 저장(중복 줄이기)
def put(store, size, layer, pts, d):
    x0, y0, x1, y1 = bbox(pts); ci, cj = int(((x0 + x1) / 2) // size), int(((y0 + y1) / 2) // size); m = size * MARG
    if x0 >= ci * size - m and x1 <= (ci + 1) * size + m and y0 >= cj * size - m and y1 <= (cj + 1) * size + m:
        store.setdefault("%d,%d" % (ci, cj), {}).setdefault(layer, []).append(d); return
    for i in range(int(x0 // size), int(x1 // size) + 1):
        for j in range(int(y0 // size), int(y1 // size) + 1):
            store.setdefault("%d,%d" % (i, j), {}).setdefault(layer, []).append(d)
def addlab(store, size, x, y, rec):
    store.setdefault("%d,%d" % (int(x // size), int(y // size)), []).append(rec)
roadlab = {}  # (tile, name) → (len, rec)
def nm(p): return (p.get("name:ko") or p.get("name") or "").strip()

n = 0
with open(src, encoding="utf-8") as f:
    for line in f:
        line = line.strip().lstrip("\x1e")
        if not line: continue
        ft = json.loads(line); g = ft.get("geometry"); p = ft.get("properties") or {}
        if not g: continue
        n += 1; gt = g["type"]
        if gt == "Point":
            x, y = proj([g["coordinates"]])[0]
            if not (0 <= x <= W and 0 <= y <= H): continue
            name = nm(p)
            if not name: continue
            pl, hw = p.get("place"), p.get("highway")
            if hw == "motorway_junction": addlab(lb1, T1S, x, y, [round(x), round(y), 0, name, "jc"])
            elif pl in ("town", "suburb"): addlab(lb1, T1S, x, y, [round(x), round(y), 0, name, "p1"])
            elif pl in ("village", "quarter", "neighbourhood"): addlab(lb2, T2S, x, y, [round(x), round(y), 0, name, "p2"])
            continue
        if gt == "LineString":
            hw, ww, rw = p.get("highway"), p.get("waterway"), p.get("railway")
            lay = RD.get(hw) or ("rw" if rw in ("rail", "light_rail") and p.get("tunnel") not in ("yes",) and p.get("service") is None else None) or {"river": "rv", "canal": "cn", "stream": "st"}.get(ww)
            if not lay: continue
            pts = proj(g["coordinates"])
            if len(pts) < 2: continue
            L = length(pts); tun = p.get("tunnel") in ("yes", "building_passage", "culvert")
            if lay in OV:
                tol, _, lmin = OV[lay]
                if L >= lmin:
                    d = enc(dp(pts, tol))
                    if d: ov.setdefault(lay, []).append(d)
            if lay in ("mi", "st"):
                if lay == "st" or L < 4: continue  # 실개천은 용량 대비 효과가 작아 제외
                d = enc(dp(pts, 1.0 if lay == "mi" else 1.4))
                if d: put(t2, T2S, lay + ("T" if tun and lay == "mi" else ""), pts, d)
            else:
                d = enc(dp(pts, 1.3 if lay in ("rv", "cn") else 0.9))
                if d: put(t1, T1S, lay + ("T" if tun and lay in ("mw", "tr", "pr", "sc", "te") else ""), pts, d)
            # 도로 이름 라벨 후보: 타일·이름별 가장 긴 구간
            name = nm(p) if lay in RD.values() else ""
            if lay in ("mw", "tr") and not name: name = (p.get("ref") or "").split(";")[0]
            if name and L >= (40 if lay in ("mw", "tr", "pr") else 25 if lay in ("sc", "te") else 30) and not tun:
                half, acc, k = L / 2, 0, 0
                for k in range(len(pts) - 1):
                    s = math.hypot(pts[k + 1][0] - pts[k][0], pts[k + 1][1] - pts[k][1])
                    if acc + s >= half: break
                    acc += s
                (ax, ay), (bx, by) = pts[k], pts[k + 1]; s = math.hypot(bx - ax, by - ay) or 1; t = (half - acc) / s
                x, y = ax + (bx - ax) * t, ay + (by - ay) * t
                ang = math.degrees(math.atan2(by - ay, bx - ax))
                if ang > 90: ang -= 180
                if ang < -90: ang += 180
                big = lay in ("mw", "tr", "pr", "sc", "te")
                key = ("1" if big else "2", "%d,%d" % (int(x // (T1S if big else T2S)), int(y // (T1S if big else T2S))), name)
                if key not in roadlab or roadlab[key][0] < L: roadlab[key] = (L, [round(x), round(y), round(ang), name, "r" + lay])
            continue
        if gt in ("Polygon", "MultiPolygon"):
            nat, lu, wat = p.get("natural"), p.get("landuse"), p.get("water")
            lay = "wt" if (nat == "water" or lu == "reservoir" or p.get("waterway") == "riverbank") else "fo" if (nat == "wood" or lu == "forest") else "ur" if lu in ("residential", "commercial", "industrial", "retail") else None
            if not lay: continue
            polys = [g["coordinates"]] if gt == "Polygon" else g["coordinates"]
            tol, amin, _ = OV[lay]
            for pg in polys:
                rings = [proj(r) for r in pg if len(r) > 3]
                if not rings: continue
                A = area(rings[0])
                if A >= amin:
                    d = "".join(enc(q, True) for q in (dp(r, tol) for r in rings) if len(q) >= 4)
                    if d: ov.setdefault(lay, []).append(d)
                elif lay == "wt" and A >= 6:
                    d = "".join(enc(q, True) for q in (dp(r, 0.8) for r in rings) if len(q) >= 4)
                    if d: put(t1 if A >= 60 else t2, T1S if A >= 60 else T2S, "wt", rings[0], d)
pts_lab = {}
for store, size in ((lb1, T1S), (lb2, T2S)):
    for k in list(store):
        keep = []
        for r in store[k]:
            if r[4] in ("jc", "p1", "p2"):
                g = pts_lab.setdefault((r[4], r[3]), [])
                if any(abs(r[0] - q[0]) + abs(r[1] - q[1]) < (250 if r[4] == "jc" else 120) for q in g): continue
                g.append(r)
            keep.append(r)
        store[k] = keep
for (lv, tile, name), (L, rec) in roadlab.items():
    (lb1 if lv == "1" else lb2).setdefault(tile, []).append(rec)
# 같은 층의 경로들을 가까운 것끼리 정렬하고, 두 번째부터는 상대 이동(m)으로 써서 용량 줄이기
_RE = re.compile(r"M(-?\d+) (-?\d+)([^Mz]*)(z?)")
_RL = re.compile(r"l(-?\d+) ?(-?\d+)")
def rel(parts):
    segs = []
    for d in parts:
        for m in _RE.finditer(d): segs.append((int(m.group(1)), int(m.group(2)), m.group(3), m.group(4)))
    segs.sort(key=lambda t: (t[1] // 40, t[0] if (t[1] // 40) % 2 == 0 else -t[0]))
    out, cx, cy = [], None, None
    for x, y, body, z in segs:
        if cx is None: out.append("M%d %d" % (x, y))
        else: dx, dy = x - cx, y - cy; out.append("m%d%s%d" % (dx, " " if dy >= 0 else "", dy))
        out.append(body + z)
        if z: cx, cy = x, y
        else:
            px, py = x, y
            for a, b in _RL.findall(body): px += int(a); py += int(b)
            cx, cy = px, py
    return "".join(out)
def join(store): return {k: {l: rel(v) for l, v in d.items()} for k, d in store.items()}
res = {"origin": [X0, Y1, U], "asof": asof, "attrib": "© OpenStreetMap contributors (ODbL)",
       "layers": {k: rel(v) for k, v in ov.items()},
       "T1": {"size": T1S, "tiles": join(t1)}, "T2": {"size": T2S, "tiles": join(t2)}, "L1": lb1, "L2": lb2}
json.dump(res, open(out_fn, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
def sz(o): return len(json.dumps(o, ensure_ascii=False, separators=(",", ":")).encode()) // 1000
print("features", n)
print("overview KB", {k: len(v) // 1000 for k, v in res["layers"].items()})
lay_t1, lay_t2 = {}, {}
for d in res["T1"]["tiles"].values():
    for l, v in d.items(): lay_t1[l] = lay_t1.get(l, 0) + len(v) // 1000
for d in res["T2"]["tiles"].values():
    for l, v in d.items(): lay_t2[l] = lay_t2.get(l, 0) + len(v) // 1000
print("T1 tiles", len(t1), "KB", lay_t1)
print("T2 tiles", len(t2), "KB", lay_t2)
print("labels L1", sum(len(v) for v in lb1.values()), sz(lb1), "KB · L2", sum(len(v) for v in lb2.values()), sz(lb2), "KB")
print("total KB", os.path.getsize(out_fn) // 1000)
