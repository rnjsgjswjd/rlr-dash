# -*- coding: utf-8 -*-
"""
도로교통공단(TAAS) 사고다발지역 Open API 전국 수집 스크립트
- 인터넷 되는 PC에서 실행 → 결과 CSV를 대시보드 [BETA TEST > 사고다발지역 > 외부 데이터 불러오기]로 넣습니다.
- 파이썬 3.8 이상, 추가 설치 없음(표준 라이브러리만 사용).

준비물
 1) data.go.kr 인증키(일반 인증키 Decoding 또는 Encoding 둘 다 가능)
 2) 쓰려는 API 활용신청 (예: 한국도로교통공단_지자체별 교통사고 다발지역, _결빙 교통사고 다발지역)
 3) 법정동코드 전체자료 (code.go.kr → 법정동코드목록조회 → '전체자료' 다운로드 → 압축 풀어 이 파일과 같은 폴더에 두기)
    파일 이름 예: 법정동코드 전체자료.txt

실행
  python 사고다발지역_수집.py
  (묻는 대로 인증키, 연도, 유형을 입력)
  또는: python 사고다발지역_수집.py --key 인증키 --years 2021 2022 2023 --types lg freezing

인증키는 이 PC에만 입력합니다. 채팅·메일 등에 붙여넣지 마세요.
"""
import argparse, csv, glob, json, os, sys, time, urllib.parse, urllib.request, urllib.error

BASE = "https://apis.data.go.kr/B552061"
TYPES = {  # 유형코드: (서비스명, 오퍼레이션명, 한글 이름)
    "lg": ("frequentzoneLg", "getRestFrequentzoneLg", "지자체별"),
    "freezing": ("frequentzoneFreezing", "getRestFrequentzoneFreezing", "결빙"),
    "oldman": ("frequentzoneOldman", "getRestFrequentzoneOldman", "보행노인"),
    "child": ("frequentzoneChild", "getRestFrequentzoneChild", "보행어린이"),
}
OUT_COLS = ["유형", "연도", "시도코드", "구군코드", "시군구", "지점명", "위도", "경도", "발생건수", "사상자수", "사망자수", "중상자수", "경상자수", "부상신고자수", "다발지역ID", "법정동코드"]


def read_codes(path):
    """법정동코드 전체자료 → [(시도2, 구군3, 이름)] (현존 시군구만)"""
    raw = open(path, "rb").read()
    for enc in ("utf-8-sig", "cp949", "euc-kr"):
        try:
            text = raw.decode(enc); break
        except UnicodeDecodeError:
            continue
    out, seen = [], set()
    for line in text.splitlines()[1:]:
        p = line.replace(",", "\t").split("\t")
        if len(p) < 3: continue
        code, name, alive = p[0].strip(), p[1].strip(), p[2].strip()
        if len(code) != 10 or alive != "존재": continue
        if code[5:] != "00000" or code[2:5] == "000": continue  # 시군구 단위만
        key = (code[:2], code[2:5])
        if key in seen: continue
        seen.add(key); out.append((code[:2], code[2:5], name))
    # 세종시는 시군구 아래 단계가 없어 '36110'로 들어오는 경우가 많음
    if not any(s == "36" for s, _, _ in out): out.append(("36", "110", "세종특별자치시"))
    return out


def call(svc, op, key, year, sido, gugun, page, rows=100, tries=3):
    q = urllib.parse.urlencode({"ServiceKey": key, "searchYearCd": year, "siDo": sido, "guGun": gugun, "type": "json", "numOfRows": rows, "pageNo": page})
    url = f"{BASE}/{svc}/{op}?{q}"
    for t in range(tries):
        try:
            with urllib.request.urlopen(url, timeout=20) as r:
                body = r.read().decode("utf-8", "replace")
            try:
                return json.loads(body)
            except json.JSONDecodeError:
                return {"resultCode": "XML", "resultMsg": body[:300]}
        except (urllib.error.URLError, TimeoutError) as e:
            if t == tries - 1: return {"resultCode": "NET", "resultMsg": str(e)}
            time.sleep(1.5 * (t + 1))


def items_of(js):
    it = js.get("items")
    if isinstance(it, dict): it = it.get("item", [])
    if isinstance(it, dict): it = [it]
    return it or []


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--key"); ap.add_argument("--years", nargs="*"); ap.add_argument("--types", nargs="*")
    ap.add_argument("--codes", help="법정동코드 전체자료 파일 경로"); ap.add_argument("--out", default="사고다발지역_수집.csv")
    a = ap.parse_args()
    here = os.path.dirname(os.path.abspath(__file__))
    key = a.key or os.environ.get("DATA_GO_KR_KEY") or input("인증키를 붙여넣으세요: ").strip()
    key = urllib.parse.unquote(key)  # Encoding 키를 넣어도 동작
    years = a.years or input("연도 (여러 개는 띄어쓰기, 예: 2021 2022 2023): ").split()
    types = a.types or (input("유형 (lg=지자체별, freezing=결빙, oldman=보행노인, child=보행어린이 / 기본 lg): ").split() or ["lg"])
    types = [t for t in types if t in TYPES] or ["lg"]
    codes_path = a.codes or next(iter(sorted(glob.glob(os.path.join(here, "*법정동*코드*.txt")) + glob.glob(os.path.join(here, "*법정동*.txt")))), None)
    if not codes_path or not os.path.exists(codes_path):
        print("\n[!] 법정동코드 전체자료 파일을 찾지 못했습니다. code.go.kr 에서 '전체자료'를 받아 이 스크립트와 같은 폴더에 두세요."); sys.exit(1)
    codes = read_codes(codes_path)
    print(f"시군구 {len(codes)}곳 · 연도 {years} · 유형 {[TYPES[t][2] for t in types]}")

    # 1) 키·API 확인 (서울 성동구)
    svc, op, _ = TYPES[types[0]]
    js = call(svc, op, key, years[0], "11", "200", 1, 5)
    rc = str(js.get("resultCode", ""))
    print(f"[확인] 응답 코드 {rc} {js.get('resultMsg', '')}")
    try: json.dump(js, open(os.path.join(here, "probe.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    except Exception: pass
    if rc not in ("00", "0", "0000", "INFO-000") and not items_of(js) and js.get("totalCount") is None:
        print("[!] 정상 응답이 아닙니다. 인증키 등록 대기(발급 후 최대 1시간), 활용신청 여부, 키 복사를 확인하세요."); sys.exit(1)

    out_path = os.path.join(here, a.out)
    n_call = n_row = 0; seen = set()  # 시(상위)와 구(하위) 코드가 겹쳐 같은 지점이 두 번 오는 경우 제거
    with open(out_path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f); w.writerow(OUT_COLS)
        for t in types:
            svc, op, tname = TYPES[t]
            for y in years:
                for i, (sd, gg, nm) in enumerate(codes):
                    page = 1
                    while True:
                        js = call(svc, op, key, y, sd, gg, page); n_call += 1
                        rc = str(js.get("resultCode", ""))
                        if rc in ("22", "LIMITED_NUMBER_OF_SERVICE_REQUESTS_EXCEEDS_ERROR"):
                            print("\n[!] 오늘 호출 한도를 넘었습니다. 내일 이어서 실행하세요(이미 받은 결과는 저장됨)."); f.flush(); return
                        its = items_of(js)
                        for it in its:
                            uid = (tname, y, it.get("afos_id"), it.get("afos_fid"), it.get("spot_cd"), it.get("la_crd"), it.get("lo_crd"))
                            if uid in seen: continue
                            seen.add(uid)
                            w.writerow([tname, y, sd, gg, it.get("sido_sgg_nm", nm), it.get("spot_nm", ""), it.get("la_crd", ""), it.get("lo_crd", ""),
                                        it.get("occrrnc_cnt", it.get("occrmc_cnt", "")), it.get("caslt_cnt", ""), it.get("dth_dnv_cnt", ""), it.get("se_dnv_cnt", ""),
                                        it.get("sl_dnv_cnt", ""), it.get("wnd_dnv_cnt", ""), it.get("afos_id", ""), it.get("bjd_cd", "")])
                            n_row += 1
                        total = int(js.get("totalCount") or 0)
                        if page * 100 >= total or not its: break
                        page += 1
                        time.sleep(0.05)
                    print(f"\r{tname} {y}년 {i + 1}/{len(codes)} {nm[:14]:<14} 누적 {n_row}건 (호출 {n_call})", end="", flush=True)
                    time.sleep(0.05)
                print()
    print(f"\n완료: {out_path}\n지점 {n_row}건 · 호출 {n_call}회 → 대시보드 [BETA TEST > 사고다발지역 > 외부 데이터 불러오기]로 넣으세요.")


if __name__ == "__main__":
    main()
