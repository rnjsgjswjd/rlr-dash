# 외부 데이터 묶음 만들기: data 브랜치의 TAAS(fz_*.csv)·TMACS(tmacs/tmacs_jijace.csv) → ext/ext_bundle.json
# 사용: python tools/ext_build.py <data 브랜치 폴더>
import csv, glob, json, os, sys, time
D = sys.argv[1] if len(sys.argv) > 1 else "."
OUT = os.path.join(D, "ext"); os.makedirs(OUT, exist_ok=True)
today = time.strftime("%Y-%m-%d")
f = lambda x: float(str(x).replace(",", "") or 0) if str(x).strip() not in ("", "None", "nan") else 0.0
SIDO = {"11": "서울", "26": "부산", "27": "대구", "28": "인천", "29": "광주", "30": "대전", "31": "울산", "36": "세종", "41": "경기", "42": "강원", "51": "강원", "43": "충북", "44": "충남", "45": "전북", "52": "전북", "46": "전남", "47": "경북", "48": "경남", "50": "제주"}

# ── TAAS ── 같은 (유형, 연도, 위치)는 한 번만, 늦게 받은 파일이 우선
files = sorted(glob.glob(os.path.join(D, "*.csv")) + glob.glob(os.path.join(D, "fz", "*.csv")), key=os.path.getmtime)
byType, src = {}, []
for fn in files:
    try: rows = list(csv.DictReader(open(fn, encoding="utf-8-sig")))
    except Exception: continue
    if not rows or "위도" not in rows[0]: continue
    src.append(os.path.basename(fn))
    for r in rows:
        try: y, la, lo = int(r["연도"]), round(float(r["위도"]), 6), round(float(r["경도"]), 6)
        except Exception: continue
        if not (33 < la < 39 and 124 < lo < 132): continue
        t = r.get("유형") or "지자체별"
        byType.setdefault(t, {})[(y, round(la, 5), round(lo, 5))] = [y, la, lo, f(r["발생건수"]), f(r["사상자수"]), f(r["사망자수"]), f(r["중상자수"]), r["지점명"].strip(), 1, r.get("시도코드", "")[:2]]
taas = {}
for t, d in byType.items():
    pts = sorted(d.values(), key=lambda p: (p[0], p[9], -p[3]))
    yrs_at = {}
    for p in pts: yrs_at.setdefault((round(p[1], 3), round(p[2], 3)), set()).add(p[0])
    for p in pts: p[8] = len(yrs_at[(round(p[1], 3), round(p[2], 3))])
    years = sorted({p[0] for p in pts})
    cover = {y: sorted({SIDO.get(p[9], p[9]) for p in pts if p[0] == y}) for y in years}
    allsd = sorted(set(SIDO.values()))
    gaps = [f"{y}년 {'·'.join(s for s in allsd if s not in cover[y])}" for y in years if len([s for s in allsd if s not in cover[y]]) and len(cover[y]) > 5]
    taas[t] = {"asof": today, "src": f"한국도로교통공단(TAAS) {t} 교통사고 다발지역 Open API", "years": years, "n": len(pts),
               "pts": [p[:9] for p in pts], "gaps": ("원천(API)에 자료가 없는 연도·시도: " + ", ".join(gaps)) if gaps else ""}
    print("TAAS", t, years, len(pts))

# ── TMACS ──
tm = None; fn = os.path.join(D, "tmacs", "tmacs_jijace.csv")
if os.path.exists(fn):
    rows, seen = [], {}
    for x in csv.DictReader(open(fn, encoding="utf-8-sig")):
        st = {"all": "a", "death": "d", "serious": "s"}.get(x.get("_stand"));
        if not st: continue
        sd, nm = x["_sido"], x["GBN"].strip()
        if (sd, nm) == ("인천", "남구"): nm = "미추홀구"
        if (sd, nm) == ("경북", "군위군"): sd = "대구"
        k = (sd, nm, x["_year"], st); row = [sd, nm, int(x["_year"]), st, f(x["CNT"]), f(x["CNT1"]), f(x["MEN"]), f(x["MEN1"]), f(x["CAR"]), f(x["CAR1"])]
        if k in seen:
            if row[4] > rows[seen[k]][4]: rows[seen[k]] = row
            continue
        seen[k] = len(rows); rows.append(row)
    tm = {"asof": today, "years": sorted({r[2] for r in rows}), "rows": rows}
    print("TMACS", tm["years"], len(rows))

kma = None; fn = os.path.join(D, "kma", "kma_asos_yearly.csv")
if os.path.exists(fn):
    rr = list(csv.DictReader(open(fn, encoding="utf-8-sig")))
    if rr:
        cols = [c for c in rr[0] if c not in ("stnId", "stnNm", "year")]
        kma = {"asof": today, "cols": cols, "years": sorted({int(r["year"]) for r in rr}), "rows": [[int(r["stnId"]), r["stnNm"], int(r["year"])] + [f(r[c]) for c in cols] for r in rr]}
        print("KMA", kma["years"], len(rr))
api = json.load(open(os.path.join(D, "ext", "api_status.json"), encoding="utf-8")) if os.path.exists(os.path.join(D, "ext", "api_status.json")) else None
main = taas.get("지자체별")
bundle = {"kind": "rlr-ext", "v": 1, "asof": today, "taas": main, "taasT": {t: v["pts"] for t, v in taas.items() if t != "지자체별"}, "tmacs": tm, "kma": kma, "api": api,
          "manifest": [{"src": "TAAS " + t, "years": v["years"], "n": v["n"], "gaps": v["gaps"]} for t, v in taas.items()] + ([{"src": "TMACS 지자체별 사고지표", "years": tm["years"], "n": len(tm["rows"])}] if tm else []) + ([{"src": "기상청 ASOS 관측소 연간 지표", "years": kma["years"], "n": len(kma["rows"])}] if kma else []), "files": src}
json.dump(bundle, open(os.path.join(OUT, "ext_bundle.json"), "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
man = {k: bundle[k] for k in ("asof", "manifest", "api")}
json.dump(man, open(os.path.join(OUT, "manifest.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
hist = os.path.join(OUT, "HISTORY.md"); old = open(hist, encoding="utf-8").read() if os.path.exists(hist) else "# 외부 데이터 갱신 이력\n\n| 날짜 | 내용 |\n|---|---|\n"
line = f"| {today} | " + " · ".join(f"{m['src']} {m['years'][0]}~{m['years'][-1]} {m['n']:,}건" for m in bundle["manifest"] if m["years"]) + " |\n"
open(hist, "w", encoding="utf-8").write(old + line)
print("bundle", os.path.getsize(os.path.join(OUT, "ext_bundle.json")), "bytes")
