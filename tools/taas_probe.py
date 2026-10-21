# TAAS(도로교통공단) 사고다발지역 API 점검: 어떤 유형이 이 인증키로 열려 있는지 확인 → api_status.json
import json, os, sys, time, urllib.parse, urllib.request, urllib.error
KEY = urllib.parse.unquote(os.environ.get("DATA_GO_KR_KEY", ""))
Y = str(int(time.strftime("%Y")) - 1)
CAND = {  # 유형코드: (서비스, 오퍼레이션, 이름)
    "lg": ("frequentzoneLg", "getRestFrequentzoneLg", "지자체별"),
    "freezing": ("frequentzoneFreezing", "getRestFrequentzoneFreezing", "결빙"),
    "oldman": ("frequentzoneOldman", "getRestFrequentzoneOldman", "보행노인"),
    "child": ("frequentzoneChild", "getRestFrequentzoneChild", "보행어린이"),
    "bicycle": ("frequentzoneBicycle", "getRestFrequentzoneBicycle", "자전거"),
    "motorcycle": ("frequentzoneMotorcycle", "getRestFrequentzoneMotorcycle", "이륜차"),
    "jaywalking": ("frequentzonePedstrians", "getRestFrequentzonePedstrians", "보행자무단횡단"),
    "holiday": ("frequentzoneHoliday", "getRestFrequentzoneHoliday", "연휴기간"),
}
out = {"checked": time.strftime("%Y-%m-%d %H:%M"), "year": Y, "types": {}}
for t, (svc, op, nm) in CAND.items():
    st, msg = "", ""
    for yy in (Y, str(int(Y) - 1)):
        q = urllib.parse.urlencode({"ServiceKey": KEY, "searchYearCd": yy, "siDo": "11", "guGun": "680", "type": "json", "numOfRows": 1, "pageNo": 1})
        try:
            body = urllib.request.urlopen(f"https://apis.data.go.kr/B552061/{svc}/{op}?{q}", timeout=25).read().decode("utf-8", "replace")
            try: js = json.loads(body); st, msg = str(js.get("resultCode", "")), js.get("resultMsg", "")
            except json.JSONDecodeError: st, msg = "XML", body[:200]
        except urllib.error.HTTPError as e:
            b = e.read().decode("utf-8", "replace"); st, msg = str(e.code), b[:200]
            try: h = json.loads(b)["OpenAPI_ServiceResponse"]["cmmMsgHeader"]; st, msg = h.get("returnReasonCode", st), h.get("returnAuthMsg", "") or h.get("errMsg", "")
            except Exception: pass
        except Exception as e: st, msg = "NET", str(e)[:200]
        if st in ("00", "03"): break
        time.sleep(0.3)
    ok = st in ("00", "03")  # 03 = 자료 없음(서비스는 열림)
    out["types"][t] = {"name": nm, "service": svc, "ok": ok, "code": st, "msg": msg, "state": "사용 가능" if ok else ("활용신청 필요" if st in ("30", "20") or "REGISTERED" in msg.upper() else ("서비스 없음/이름 다름" if st in ("404", "XML") else "오류"))}
    print(t, nm, st, msg[:80])
json.dump(out, open(sys.argv[1] if len(sys.argv) > 1 else "api_status.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("AVAILABLE", " ".join(t for t, v in out["types"].items() if v["ok"]))
