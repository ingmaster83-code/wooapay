"""
fetch_pay.py — 전국지역화폐가맹점표준데이터 다운로드
data.go.kr download/standard.json 직접 다운로드 (API 키 불필요)

publicDataPk=15100062, svcTableNm=tn_pubr_public_local_bill_svc
컬럼: 가맹점명, 사용가능지역화폐, 시도명, 시군구명, 도로명주소, 지번주소, 업종명, 주요상품, 전화번호, 기준일자
좌표(위도/경도) 컬럼은 원본에 없음 — 주소 기반 지도 링크만 제공 가능.

※ 주의: data.go.kr UI/columList.json에는 totalCount가 50000으로 표시되지만
   이는 그리드뷰 표시 상한일 뿐, 실제로는 perPage=10000으로 페이지네이션하면
   181,710건(19페이지) 전부 받아올 수 있음이 확인됨(2026-09-02).
※ 주의: INSTT_CODE/INSTT_NM(제공기관코드/명)은 서버가 응답에 항상 자동으로 붙여주는
   필드라 colNmList에 명시적으로 다시 넣으면 API가 200/빈바디로 조용히 실패함 — 요청에서 제외.
"""
import json
import time
from pathlib import Path
import requests

BASE = "https://www.data.go.kr/download/standard.json"
PUBLIC_DATA_PK = "15100062"
SVC_TABLE = "tn_pubr_public_local_bill_svc"

COLUMNS = [
    "AFFILIATE_NM", "LOCAL_BILL", "CTPV_NM", "SGG_NM",
    "LCTN_ROAD_NM_ADDR", "LCTN_LOTNO_ADDR", "SECTOR_NM", "MAIN_PRD",
    "TELNO", "CRTR_YMD",
]

OUT = Path(__file__).parent.parent / "_rawdata" / "pay_raw.json"


def fetch_all():
    total = []
    page = 1
    while True:
        params = [("publicDataPk", PUBLIC_DATA_PK)] + [("colNmList", c) for c in COLUMNS] + [
            ("totalCount", "300000"), ("svcTableNm", SVC_TABLE),
            ("perPage", "10000"), ("page", str(page)),
        ]
        r = requests.get(BASE, params=params, headers={"User-Agent": "Mozilla/5.0"}, timeout=90)
        data = r.json()
        if isinstance(data, dict) or not data:
            break
        total.extend(data)
        print(f"page {page}: {len(data)} (cumulative {len(total)})")
        if len(data) < 10000:
            break
        page += 1
        time.sleep(0.2)
    return total


def main():
    items = fetch_all()

    # 50% 안전장치: 기존 파일보다 절반 미만이면 저장 중단
    if OUT.exists():
        try:
            old = json.loads(OUT.read_text(encoding="utf-8"))
            if len(items) < len(old) * 0.5:
                print(f"경고: 새 데이터({len(items)})가 기존({len(old)})의 50% 미만 — 저장 중단")
                return
        except Exception:
            pass

    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(items, ensure_ascii=False), encoding="utf-8")
    print(f"\n총 {len(items)}건 저장 → {OUT}")


if __name__ == "__main__":
    main()
