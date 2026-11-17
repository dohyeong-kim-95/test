# 대한민국 팩트 대시보드

국제기관의 공개 지표로 대한민국의 민주주의·자유 수준을 확인하는 모바일 PWA.

| 지표 | 출처 |
|---|---|
| 체제 분류, 자유민주주의·선거민주주의 지수 | V-Dem (Our World in Data) |
| 자유 점수 (정치적 권리 + 시민 자유) | Freedom House (Our World in Data) |
| 언론자유지수 (2022~) | 국경없는기자회(RSF) |

비교 대상: 일본, 대만, 미국, 독일, 세계 평균

## 구조

- `pipeline/fetch.py` — 공개 데이터를 받아 `web/public/data/indices.json` 생성 (Python 표준 라이브러리만 사용)
- `web/` — Vite + ECharts 정적 PWA. 서버 없이 CDN에서 서빙
- `.github/workflows/deploy.yml` — 매일 데이터 갱신 후 GitHub Pages 배포

## 로컬 실행

```bash
python pipeline/fetch.py
cd web && npm install && npm run dev
```

## 배포

저장소 Settings → Pages → Source를 **GitHub Actions**로 설정하면, `main`에 푸시할 때와 매일 06:17(KST)에 자동 배포된다.
