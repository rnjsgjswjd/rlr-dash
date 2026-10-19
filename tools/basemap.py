# OSM(GeoJSON, EPSG:5179) → 대시보드 지도 좌표 SVG path (도로·철도·하천·호소·산림·시가지)
import json, os, sys, math
X0, Y1, U = 741111.0312999999, 2073441.1553000007, 10.0
def P(x, y): return (round((x - X0) / U), round((Y1 - y) / U))
def ring_area(r):
    a = 0
    for i in range(len(r) - 1): a += r[i][0] * r[i + 1][1] - r[i + 1][0] * r[i][1]
    return abs(a) / 2
def line_d(coords, mind):
    pts = [P(*c[:2]) for c in coords]; out = [pts[0]]
    for p in pts[1:]:
        if abs(p[0] - out[-1][0]) + abs(p[1] - out[-1][1]) >= mind: out.append(p)
    if len(out) < 2: return ""
    s = "M%d %d" % out[0]; px, py = out[0]
    for x, y in out[1:]: s += "l%d %d" % (x - px, y - py); px, py = x, y
    return s
def poly_d(rings, mind):
    return "".join((line_d(r, mind) + "z") for r in rings if len(r) > 3)
def load(fn):
    if not os.path.exists(fn): return []
    return json.load(open(fn, encoding="utf-8")).get("features", [])
out, stats = {}, {}
def add(layer, d):
    if d: out.setdefault(layer, []).append(d)
# 선형
for f in load("lines.geojson"):
    g, pr = f["geometry"], f["properties"]
    if not g: continue
    hw, ww, rw = pr.get("highway"), pr.get("waterway"), pr.get("railway")
    lay = "mw" if hw in ("motorway",) else "tr" if hw in ("trunk",) else "pr" if hw in ("primary",) else "sc" if hw in ("secondary",) else "rw" if rw == "rail" else "rv" if ww == "river" else "cn" if ww in ("canal",) else None
    if not lay: continue
    lines = [g["coordinates"]] if g["type"] == "LineString" else g["coordinates"] if g["type"] == "MultiLineString" else []
    for ln in lines: add(lay, line_d(ln, 2))
# 면형
MIN = {"wt": 4e4 / 100, "fo": 1.5e6 / 100, "ur": 2e5 / 100}  # m² → (10m)² 단위
for f in load("polys.geojson"):
    g, pr = f["geometry"], f["properties"]
    if not g: continue
    nat, lu = pr.get("natural"), pr.get("landuse")
    lay = "wt" if (nat == "water" or lu == "reservoir") else "fo" if (nat == "wood" or lu == "forest") else "ur" if lu in ("residential", "commercial", "industrial", "retail") else None
    if not lay: continue
    polys = [g["coordinates"]] if g["type"] == "Polygon" else g["coordinates"] if g["type"] == "MultiPolygon" else []
    for pg in polys:
        rings = [[P(*c[:2]) for c in r] for r in pg]
        if not rings or ring_area(rings[0]) < MIN[lay]: continue
        add(lay, poly_d([[(x * U + X0, Y1 - y * U) for x, y in r] for r in rings], 2))
res = {k: "".join(v) for k, v in out.items()}
for k, v in res.items(): stats[k] = (len(out[k]), len(v))
json.dump({"origin": [X0, Y1, U], "layers": res, "attrib": "© OpenStreetMap contributors (ODbL)"}, open("basemap.json", "w"), separators=(",", ":"))
print(json.dumps(stats), os.path.getsize("basemap.json"))
