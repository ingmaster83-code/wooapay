#!/usr/bin/env python3
"""
process_data.py - 원본 데이터를 Jekyll 페이지 생성용 JSON으로 가공 (시도별 분할)

입력: _rawdata/pay_raw.json (181,710건)
출력: _rawdata/pay_{도}.json x13 (시도별 분할, 100MB 파일크기 제한 회피)
      search_index.json (검색용, 루트)

사용법:
  python scripts/process_data.py [--limit N]
"""
import json, re, hashlib, sys, argparse
from pathlib import Path
from collections import Counter, defaultdict

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).parent.parent
RAW = ROOT / "_rawdata" / "pay_raw.json"
RAWDATA_DIR = ROOT / "_rawdata"
SEARCH_INDEX_OUT = ROOT / "search_index.json"

# 동/읍/면 추출 — 지번주소 우선(있으면 항상 시군구 바로 다음 토큰), 없으면 도로명주소에서
# "시/군/구" 다음 토큰 또는 괄호 안 법정동 표기("...(마곡동)")를 시도.
# "OO동1가/2가"(옛 법정동 세분화 표기)도 포함. 도로명(...로/...길)만 있고 동 정보가
# 전혀 없는 주소는 추출 불가 — 이 경우 dong=""(시군구 페이지의 "기타" 버킷으로 귀속).
_DONG_RE1 = re.compile(r"(?:시|군|구)\s+([가-힣0-9]+동(?:\d+가)?|[가-힣0-9]+(?:읍|면))(?:\s|\(|$)")
_DONG_RE2 = re.compile(r"\(([가-힣0-9]+동(?:\d+가)?)[,)]")


def extract_dong(addr: str):
    if not addr:
        return None
    m = _DONG_RE1.search(addr)
    if m:
        return m.group(1)
    m2 = _DONG_RE2.search(addr)
    if m2:
        return m2.group(1)
    return None


DO_MAP = {
    "서울특별시": "서울", "부산광역시": "부산", "대구광역시": "대구",
    "인천광역시": "인천", "광주광역시": "광주", "대전광역시": "대전",
    "울산광역시": "울산", "세종특별자치시": "세종", "경기도": "경기",
    "강원특별자치도": "강원", "강원도": "강원",
    "충청북도": "충북", "충청남도": "충남",
    "전북특별자치도": "전북", "전라북도": "전북", "전라남도": "전남",
    "경상북도": "경북", "경상남도": "경남", "제주특별자치도": "제주", "제주도": "제주",
}


def guess_sido(ctpv: str, sggu: str):
    text = (ctpv or "").strip()
    sggu = (sggu or "").strip()
    if text == "전남광주통합특별시":
        return "광주" if sggu.endswith("구") else "전남"
    return DO_MAP.get(text, "")


def make_slug(name: str, bill: str, addr: str) -> str:
    slug = re.sub(r"[^\w가-힣\s-]", "", name).strip()
    slug = re.sub(r"\s+", "-", slug)
    slug = re.sub(r"-+", "-", slug)
    h = hashlib.md5(f"{name}|{bill}|{addr}".encode("utf-8")).hexdigest()[:6]
    return f"{slug}-{h}" if slug else h


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None, help="로컬 미리보기용: 앞에서 N개만 처리")
    args = ap.parse_args()

    raw = json.loads(RAW.read_text(encoding="utf-8"))
    if args.limit:
        raw = raw[:args.limit]
        print(f"[--limit] 상위 {len(raw)}개만 처리 (로컬 미리보기 모드)")

    items = []
    seen_slugs = Counter()
    skipped = 0
    for d in raw:
        # 필드명 주의: Jekyll 내장 Page.name과 충돌하므로 "storeName" 사용
        store_name = (d.get("AFFILIATE_NM") or "").strip()
        do_full = (d.get("CTPV_NM") or "").strip()
        sigungu = (d.get("SGG_NM") or "").strip()
        addr = (d.get("LCTN_ROAD_NM_ADDR") or "").strip() or (d.get("LCTN_LOTNO_ADDR") or "").strip()
        local_bill = (d.get("LOCAL_BILL") or "").strip()
        if not store_name or not addr:
            skipped += 1
            continue

        do_short = guess_sido(do_full, sigungu)
        if not do_short or not sigungu:
            skipped += 1
            continue

        lotno_addr = (d.get("LCTN_LOTNO_ADDR") or "").strip()
        dong = extract_dong(lotno_addr) or extract_dong(addr) or "기타"

        slug = make_slug(store_name, local_bill, addr)
        seen_slugs[slug] += 1
        if seen_slugs[slug] > 1:
            slug = f"{slug}-{seen_slugs[slug]}"

        items.append({
            "storeName": store_name,
            "doShort": do_short,
            "doFull": do_full,
            "sigungu": sigungu,
            "dong": dong,
            "addr": addr,
            "localBill": local_bill,
            "sector": (d.get("SECTOR_NM") or "").strip(),
            "mainProduct": (d.get("MAIN_PRD") or "").strip(),
            "tel": (d.get("TELNO") or "").strip(),
            "refDate": (d.get("CRTR_YMD") or "").strip(),
            "slug": slug,
        })

    # 시도별로 그룹핑 후 각각 별도 파일로 저장 (git 100MB 파일 제한 회피)
    by_do = defaultdict(list)
    for i in items:
        by_do[i["doShort"]].append(i)

    RAWDATA_DIR.mkdir(parents=True, exist_ok=True)
    for do, group in by_do.items():
        out = RAWDATA_DIR / f"pay_{do}.json"
        out.write_text(json.dumps(group, ensure_ascii=False), encoding="utf-8")
        size_mb = out.stat().st_size / 1024 / 1024
        print(f"  {do}: {len(group)}개 → {out.name} ({size_mb:.1f}MB)")

    print(f"\n총 {len(items)}개 저장 (시도 {len(by_do)}개 파일로 분할, 제외: {skipped}건)")

    do_counts = Counter(i["doShort"] for i in items)
    print("\n지역별 수:")
    for do, cnt in sorted(do_counts.items(), key=lambda x: -x[1]):
        print(f"  {do}: {cnt}개")

    sigungu_counts = Counter((i["doShort"], i["sigungu"]) for i in items)
    print(f"\n시군구 조합 수: {len(sigungu_counts)}개")
    print("최다 시군구 top5:")
    for (do, sg), cnt in sigungu_counts.most_common(5):
        print(f"  {do} {sg}: {cnt}개")

    dong_counts = Counter((i["doShort"], i["sigungu"], i["dong"]) for i in items)
    no_dong = sum(1 for i in items if i["dong"] == "기타")
    print(f"\n동/읍/면 조합 수: {len(dong_counts)}개 (동 추출 실패 → '기타' 처리: {no_dong}개, {no_dong/len(items)*100:.1f}%)")
    print("최다 동 top5:")
    for (do, sg, dg), cnt in dong_counts.most_common(5):
        print(f"  {do} {sg} {dg}: {cnt}개")

    # 검색 인덱스 (짧은 키로 용량 최소화)
    index = [
        {"n": i["storeName"], "s": i["slug"], "do": i["doShort"], "sg": i["sigungu"], "dg": i["dong"]}
        for i in items
    ]
    SEARCH_INDEX_OUT.write_text(json.dumps(index, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    size_mb = SEARCH_INDEX_OUT.stat().st_size / 1024 / 1024
    print(f"\n검색 인덱스 {len(index)}건 저장 → {SEARCH_INDEX_OUT} ({size_mb:.1f}MB)")


if __name__ == "__main__":
    main()
