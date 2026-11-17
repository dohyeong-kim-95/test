import * as echarts from "echarts/core";
import { LineChart } from "echarts/charts";
import { GridComponent, TooltipComponent, LegendComponent } from "echarts/components";
import { CanvasRenderer } from "echarts/renderers";
import "./style.css";

echarts.use([LineChart, GridComponent, TooltipComponent, LegendComponent, CanvasRenderer]);

const dark = matchMedia("(prefers-color-scheme: dark)").matches;
const COLORS = { KOR: "#e4572e", JPN: "#4e79a7", TWN: "#59a14f", USA: "#b07aa1", DEU: "#edc948", WLD: "#9c9c9c" };
const REGIME_CLASS = { "자유 민주주의": "r4", "선거 민주주의": "r3", "선거 권위주의": "r2", "폐쇄적 독재": "r1" };

const fmt = (v, max) => (max === 1 ? v.toFixed(2) : v.toFixed(1));
const src = (s) => `<a href="${s.url}" target="_blank" rel="noopener">${s.name}</a>`;

function regimeCard(regime) {
  const hist = regime.history;
  const [year, label] = hist[hist.length - 1];
  const chips = hist.slice(-12).map(([y, l]) => `<span class="chip ${REGIME_CLASS[l] || ""}" title="${y}: ${l}">${String(y).slice(2)}</span>`).join("");
  return `<section class="card">
    <h2>체제 분류 <small>V-Dem</small></h2>
    <div class="big">${label} <small>(${year}년)</small></div>
    <div class="chips">${chips}</div>
    <div class="legend-row">${Object.entries(REGIME_CLASS).map(([l, c]) => `<span><i class="chip ${c}"></i>${l}</span>`).join("")}</div>
    <p class="muted">연도별 대한민국 분류 (최근 12년). 출처: ${src(regime.source)}</p>
  </section>`;
}

function indicatorCard(ind) {
  const kor = ind.series.KOR;
  const [year, val] = kor[kor.length - 1];
  const prev = kor[kor.length - 2];
  const diff = prev ? val - prev[1] : 0;
  const arrow = diff > 0 ? "▲" : diff < 0 ? "▼" : "–";
  return `<section class="card">
    <h2>${ind.title} <small>${ind.org}</small></h2>
    <div class="big">${fmt(val, ind.max)} <small>/ ${ind.max} (${year}년)</small>
      <span class="delta ${diff > 0 ? "up" : diff < 0 ? "down" : ""}">${arrow} ${fmt(Math.abs(diff), ind.max)}</span></div>
    <p class="desc">${ind.desc}</p>
    <div class="chart" id="chart-${ind.id}"></div>
    <p class="muted">출처: ${src(ind.source)}</p>
  </section>`;
}

function drawChart(ind, names) {
  const chart = echarts.init(document.getElementById(`chart-${ind.id}`), dark ? "dark" : null, { renderer: "canvas" });
  chart.setOption({
    backgroundColor: "transparent",
    tooltip: { trigger: "axis", valueFormatter: (v) => (v == null ? "-" : fmt(v, ind.max)) },
    legend: { bottom: 0, itemWidth: 14, textStyle: { fontSize: 11 } },
    grid: { left: 36, right: 16, top: 12, bottom: 72 },
    xAxis: { type: "value", min: "dataMin", max: "dataMax", minInterval: 1, axisLabel: { formatter: (v) => v } },
    yAxis: { type: "value", min: ind.min, max: ind.max },
    series: Object.entries(ind.series).map(([code, data]) => ({
      name: names[code], type: "line", data, showSymbol: data.length < 8,
      lineStyle: { width: code === "KOR" ? 3 : 1.5, type: code === "WLD" ? "dashed" : "solid" },
      color: COLORS[code], z: code === "KOR" ? 10 : 1,
    })),
  });
  addEventListener("resize", () => chart.resize());
}

async function main() {
  const app = document.getElementById("app");
  try {
    const res = await fetch(`${import.meta.env.BASE_URL}data/indices.json`);
    const data = await res.json();
    app.innerHTML = regimeCard(data.regime) + data.indicators.map(indicatorCard).join("");
    data.indicators.forEach((ind) => drawChart(ind, data.countries));
    document.getElementById("footer").innerHTML =
      `데이터 갱신일: ${data.updated} · 각 기관의 연례 보고서 기준이며, 수치는 기관마다 평가 방식이 다릅니다.`;
  } catch (e) {
    app.innerHTML = `<p class="muted">데이터를 불러오지 못했습니다. (${e.message})</p>`;
  }
}

main();
