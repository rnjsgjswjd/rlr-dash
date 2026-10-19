# TMACS(교통안전정보관리시스템) 지자체별 사고지표 현황 수집 → CSV
import json, re, sys, time, urllib.parse, urllib.request, http.cookiejar, csv, os
BASE = "https://tmacs.kotsa.or.kr"
cj = http.cookiejar.CookieJar(); op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
op.addheaders = [("User-Agent", "Mozilla/5.0"), ("Referer", BASE + "/web/TG/TG200/TG2100/Tg2114.jsp?mid=S1894")]
page = op.open(BASE + "/web/TG/TG200/TG2100/Tg2114.jsp?mid=S1894", timeout=60).read().decode("utf-8", "replace")
years = re.findall(r"SetYear\('1','\d+','(\d+)'\)", page)
sidos = re.findall(r"SetArray\('1','\d+','(\d+)','([^']+)'\)", page)
os.makedirs("out", exist_ok=True)
open("out/meta.json", "w").write(json.dumps({"years": years, "sidos": sidos}, ensure_ascii=False))
want = [y for y in years if y >= "2019"]
rows, raw = [], {}
for stand in ["all", "death", "serious"]:
    for y in want:
        for code, nm in sidos:
            data = urllib.parse.urlencode({"mid": "S1894", "sido": code, "stand": stand, "sYear": y, "eYear": y, "jijace_cls": "99"}).encode()
            txt = ""
            for t in range(6):
                try:
                    txt = op.open(BASE + "/web/TG/TG200/TG2100/Tg2114_AJAX.jsp", data=data, timeout=90).read().decode("utf-8", "replace").strip()
                    if txt.startswith("["): break
                except Exception as e:
                    txt = "ERR " + str(e)
                time.sleep(3 + 3 * t)
            raw[f"{stand}_{y}_{code}"] = txt[:20000]
            try:
                arr = json.loads(txt)
            except Exception:
                arr = []
            for r in arr if isinstance(arr, list) else []:
                r = dict(r); r.update({"_stand": stand, "_year": y, "_sido": nm, "_sidocd": code}); rows.append(r)
            time.sleep(0.8)
json.dump(raw, open("out/raw.json", "w"), ensure_ascii=False)
keys = sorted({k for r in rows for k in r})
with open("out/tmacs_jijace.csv", "w", newline="", encoding="utf-8-sig") as f:
    w = csv.DictWriter(f, fieldnames=keys); w.writeheader(); [w.writerow(r) for r in rows]
bad = [k for k, v in raw.items() if not v.startswith("[")]
print("years", years, "rows", len(rows), "failed", len(bad), bad[:30], "keys", keys)
