# 기상청 지상(종관, ASOS) 일자료 → 관측소·연도별 침수/결빙 위험 지표 (공공데이터포털 같은 인증키)
# 사용: python tools/kma_asos.py <연도들: 2019-2025> <출력 csv>
import csv, json, os, sys, time, urllib.parse, urllib.request, urllib.error
KEY = urllib.parse.unquote(os.environ.get("DATA_GO_KR_KEY", ""))
URL = "https://apis.data.go.kr/1360000/AsosDalyInfoService/getWthrDataList"
STN = [90,93,95,98,99,100,101,102,104,105,106,108,112,114,115,119,121,127,129,130,131,133,135,136,137,138,140,143,146,152,155,156,159,162,165,168,169,170,172,174,175,177,184,185,188,189,192,201,202,203,211,212,216,217,221,226,232,235,236,238,239,243,244,245,247,248,251,252,253,254,255,257,258,259,260,261,262,263,264,266,268,271,272,273,276,277,278,279,281,283,284,285,288,289,294,295]
def years(s):
    if "-" in s: a, b = s.split("-"); return list(range(int(a), int(b) + 1))
    return [int(x) for x in s.split()]
def call(stn, y):
    q = urllib.parse.urlencode({"serviceKey": KEY, "pageNo": 1, "numOfRows": 400, "dataType": "JSON", "dataCd": "ASOS", "dateCd": "DAY", "startDt": f"{y}0101", "endDt": f"{y}1231" if y < int(time.strftime("%Y")) else time.strftime("%Y%m%d", time.localtime(time.time() - 2 * 86400)), "stnIds": stn})
    for t in range(4):
        try:
            js = json.loads(urllib.request.urlopen(f"{URL}?{q}", timeout=40).read().decode("utf-8", "replace"))
            h = js.get("response", {}).get("header", {}); its = (((js.get("response", {}).get("body") or {}).get("items") or {}).get("item")) or []
            return h.get("resultCode", ""), h.get("resultMsg", ""), its
        except urllib.error.HTTPError as e:
            b = e.read().decode("utf-8", "replace")
            return str(e.code), b[:200], []
        except Exception as e:
            err = str(e); time.sleep(2 + 2 * t)
    return "NET", err, []
f = lambda v: float(v) if str(v).strip() not in ("", "None") else None
def main():
    ys = years(sys.argv[1]); out = sys.argv[2]
    code, msg, _ = call(108, ys[-1]); print("probe", code, msg[:120])
    if code not in ("00",): print("NOT_AVAILABLE"); json.dump({"ok": False, "code": code, "msg": msg}, open(out + ".status.json", "w"), ensure_ascii=False); return
    rows = []
    for s in STN:
        for y in ys:
            c, m, its = call(s, y)
            if not its: continue
            nm = its[0].get("stnNm", "")
            d = {"호우일수": 0, "강한비일수": 0, "결빙위험일수": 0, "영하일수": 0, "한파일수": 0, "적설일수": 0, "일수": len(its)}
            for it in its:
                rn, mn, sn = f(it.get("sumRn")), f(it.get("minTa")), f(it.get("ddMes"))
                if rn is not None and rn >= 80: d["호우일수"] += 1
                if rn is not None and rn >= 30: d["강한비일수"] += 1
                if mn is not None and mn < 0: d["영하일수"] += 1
                if mn is not None and mn <= -12: d["한파일수"] += 1
                if sn is not None and sn > 0: d["적설일수"] += 1
                if mn is not None and mn <= 0 and ((rn or 0) > 0 or (sn or 0) > 0): d["결빙위험일수"] += 1
            rows.append({"stnId": s, "stnNm": nm, "year": y, **d}); time.sleep(0.15)
        print(s, nm if rows else "", flush=True)
    with open(out, "w", newline="", encoding="utf-8-sig") as fp:
        w = csv.DictWriter(fp, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
    json.dump({"ok": True, "rows": len(rows), "years": ys}, open(out + ".status.json", "w"), ensure_ascii=False); print("rows", len(rows))
main()
