"""공적 지수 데이터를 받아 web/public/data/indices.json 으로 저장한다.

사용법: python pipeline/fetch.py
표준 라이브러리만 사용한다.
"""
import csv
import datetime as dt
import io
import json
import statistics
import urllib.error
import urllib.request
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "web" / "public" / "data" / "indices.json"
COUNTRIES = {"KOR": "대한민국", "JPN": "일본", "TWN": "대만", "USA": "미국", "DEU": "독일"}
WORLD = "WLD"
START_YEAR = 1980

OWID = "https://ourworldindata.org/grapher/{slug}.csv?v=1&csvType=full&useColumnShortNames=true"
RSF = "https://rsf.org/sites/default/files/import_classement/{year}.csv"

REGIME_KO = {
    "Closed autocracy": "폐쇄적 독재",
    "Electoral autocracy": "선거 권위주의",
    "Electoral democracy": "선거 민주주의",
    "Liberal democracy": "자유 민주주의",
}


def get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "public-data-dashboard/0.1"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def owid_rows(slug: str):
    return list(csv.DictReader(io.StringIO(get(OWID.format(slug=slug)).decode("utf-8"))))


def owid_series(slug: str, col: str, world_from_owid: bool):
    """{code: [[year, value], ...]} 반환. 세계 평균은 OWID World 행 또는 국가 평균."""
    series = {c: [] for c in COUNTRIES}
    by_year = {}
    for r in owid_rows(slug):
        if not r[col]:
            continue
        year, val, code = int(r["year"]), float(r[col]), r["code"]
        if year < START_YEAR:
            continue
        if code in series:
            series[code].append([year, val])
        if world_from_owid and code == "OWID_WRL":
            by_year[year] = [val]
        elif not world_from_owid and code and not code.startswith("OWID_"):
            by_year.setdefault(year, []).append(val)
    series[WORLD] = [[y, round(statistics.mean(v), 3)] for y, v in sorted(by_year.items())]
    return series


def freedom_house():
    pr = owid_series("political-rights-score-fh", "polrights_score", False)
    cl = owid_series("civil-liberties-score-fh", "civlibs_score", False)
    out = {}
    for code in pr:
        cl_map = dict(map(tuple, cl[code]))
        out[code] = [[y, round(v + cl_map[y], 1)] for y, v in pr[code] if y in cl_map]
    return out


def rsf():
    series = {c: [] for c in COUNTRIES}
    series[WORLD] = []
    for year in range(2022, dt.date.today().year + 1):
        try:
            raw = get(RSF.format(year=year)).decode("utf-8-sig", errors="replace")
        except urllib.error.HTTPError:
            continue
        rows = list(csv.reader(io.StringIO(raw), delimiter=";"))
        head = [h.strip() for h in rows[0]]
        iso, score = head.index("ISO"), next(i for i, h in enumerate(head) if h.startswith("Score") and "N-1" not in h)
        vals = {}
        for r in rows[1:]:
            if len(r) > score and r[score].strip():
                vals[r[iso]] = float(r[score].replace(",", "."))
        for c in COUNTRIES:
            if c in vals:
                series[c].append([year, vals[c]])
        series[WORLD].append([year, round(statistics.mean(vals.values()), 2)])
    return series


def regime():
    hist = [[int(r["year"]), r["regime_row_owid"]] for r in owid_rows("political-regime")
            if r["code"] == "KOR" and int(r["year"]) >= START_YEAR]
    return [[y, REGIME_KO.get(v, v)] for y, v in hist]


def main():
    vdem_src = {"name": "V-Dem (Our World in Data 가공)", "url": "https://ourworldindata.org/grapher/liberal-democracy-index"}
    indicators = [
        {
            "id": "libdem", "title": "자유민주주의 지수", "org": "V-Dem",
            "desc": "선거뿐 아니라 법치·사법 독립·시민 자유까지 반영. 0~1, 높을수록 민주적.",
            "min": 0, "max": 1, "series": owid_series("liberal-democracy-index", "libdem_vdem__estimate_best", True),
            "source": vdem_src,
        },
        {
            "id": "electdem", "title": "선거민주주의 지수", "org": "V-Dem",
            "desc": "자유롭고 공정한 선거, 표현·결사의 자유 수준. 0~1, 높을수록 민주적.",
            "min": 0, "max": 1, "series": owid_series("electoral-democracy-index", "electdem_vdem__estimate_best", True),
            "source": {**vdem_src, "url": "https://ourworldindata.org/grapher/electoral-democracy-index"},
        },
        {
            "id": "fh", "title": "자유 점수", "org": "Freedom House",
            "desc": "정치적 권리(40점) + 시민 자유(60점). 0~100, 높을수록 자유.",
            "min": 0, "max": 100, "series": freedom_house(),
            "source": {"name": "Freedom House (Our World in Data 가공)", "url": "https://freedomhouse.org/report/freedom-world"},
        },
        {
            "id": "rsf", "title": "언론자유지수", "org": "국경없는기자회(RSF)",
            "desc": "0~100, 높을수록 언론이 자유로움. 2022년 산정 방식 변경으로 2022년부터 표시.",
            "min": 0, "max": 100, "series": rsf(),
            "source": {"name": "RSF World Press Freedom Index", "url": "https://rsf.org/en/index"},
        },
    ]
    data = {
        "updated": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d"),
        "countries": {**COUNTRIES, WORLD: "세계 평균"},
        "regime": {"history": regime(), "source": {"name": "V-Dem 체제 분류 (Our World in Data 가공)", "url": "https://ourworldindata.org/grapher/political-regime"}},
        "indicators": indicators,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"saved {OUT} ({OUT.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
