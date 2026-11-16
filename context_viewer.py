"""Claude Code 세션 1개의 컨텍스트 구성을 트리맵(HTML)으로 시각화하고,
클릭으로 고른 항목을 바탕으로 /compact 지시문을 만들어 주는 MVP.

트리맵 조작:
    - 항목(가장 작은 네모) 클릭: 기본 → 버림 → 남김 → 기본 순으로 바뀜
    - 카테고리 클릭: 확대 / 상단 경로 클릭: 축소

사용법:
    pip install plotly
    python context_viewer.py ~/.claude/projects/<프로젝트>/<세션ID>.jsonl -o context.html
"""
import argparse
import json
from pathlib import Path

import plotly.express as px
import plotly.graph_objects as go


def est_tokens(text: str) -> int:
    # 대략적 추정: ASCII는 4글자당 1토큰, 한글 등 비ASCII는 1글자당 1토큰
    ascii_n = sum(1 for ch in text if ord(ch) < 128)
    return ascii_n // 4 + (len(text) - ascii_n)


def to_text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(to_text(b.get("text") or b.get("content") or "") for b in content)
    return json.dumps(content, ensure_ascii=False)


def short(s: str, n: int = 50) -> str:
    s = " ".join(s.split())
    return s[:n] + ("…" if len(s) > n else "")


def tool_label(name: str, inp: dict) -> str:
    key = next((k for k in ("file_path", "command", "pattern", "query", "url", "description") if k in inp), None)
    return f"{name}: {short(str(inp[key]), 40)}" if key else name


def parse_session(path: Path):
    items = []  # (category, label, tokens)
    tool_names = {}  # tool_use_id -> label
    seen_thinking = set()
    last_usage = None

    for line in path.open(encoding="utf-8"):
        d = json.loads(line)
        if d.get("isSidechain"):  # 서브에이전트 대화는 메인 컨텍스트에 없음
            continue
        t = d.get("type")

        if t == "system" and d.get("subtype") == "compact_boundary":
            items.clear()  # 압축 이후 내용만 현재 컨텍스트
            continue

        if t == "attachment":
            text = "".join(r.get("content", "") for r in d.get("rendered") or [])
            if text:
                items.append(("System reminders", d["attachment"].get("type", "?"), est_tokens(text)))
            continue

        msg = d.get("message") or {}
        content = msg.get("content")

        if t == "user":
            if isinstance(content, str):
                items.append(("User message", short(content), est_tokens(content)))
                continue
            for b in content or []:
                if b.get("type") == "tool_result":
                    label = tool_names.get(b.get("tool_use_id"), "?")
                    items.append(("Tool result", label, est_tokens(to_text(b.get("content")))))
                elif b.get("type") == "text":
                    items.append(("User message", short(b["text"]), est_tokens(b["text"])))

        elif t == "assistant":
            usage = msg.get("usage")
            if usage:
                last_usage = usage
            for b in content or []:
                bt = b.get("type")
                if bt == "text":
                    items.append(("Assistant text", short(b["text"]), est_tokens(b["text"])))
                elif bt == "tool_use":
                    label = tool_label(b["name"], b.get("input") or {})
                    tool_names[b["id"]] = label
                    items.append(("Tool call", label, est_tokens(json.dumps(b.get("input"), ensure_ascii=False))))
                elif bt == "thinking" and msg.get("id") not in seen_thinking:
                    seen_thinking.add(msg.get("id"))
                    n = (usage or {}).get("output_tokens_details", {}).get("thinking_tokens") or est_tokens(b.get("thinking", ""))
                    if n:
                        items.append(("Thinking", f"thinking {len(seen_thinking)}", n))

    total = 0
    if last_usage:
        total = sum(last_usage.get(k, 0) for k in ("input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens"))
    rest = total - sum(n for _, _, n in items)
    if rest > 0:
        items.append(("System prompt + tools (추정)", "system prompt / tool defs / CLAUDE.md", rest))
    return items, total


# 압축으로 줄일 수 없는 영역 (클릭 선택 대상에서 제외)
FIXED = {"System prompt + tools (추정)", "System reminders", "Free space"}

PANEL = """
<div style="font-family:sans-serif;padding:8px 12px">
  <div style="margin-bottom:6px">
    <span style="background:#555;color:#fff;padding:2px 6px">버림</span>
    <span style="background:#f2c94c;padding:2px 6px">남김</span>
    항목 클릭으로 선택 · 카테고리 클릭은 확대
  </div>
  <textarea id="extra" rows="2" style="width:100%" placeholder="추가 지시 (선택)"></textarea>
  <textarea id="prompt" rows="5" style="width:100%;margin-top:6px" readonly></textarea>
  <button id="copy">복사</button> <span id="sum"></span>
</div>
<script>
const gd = document.getElementById("tm");
const tr = gd.data[0];
const baseColors = tr.marker.colors.slice(), baseLabels = tr.labels.slice();
const state = {};  // idx -> "drop" | "keep"
const NEXT = {undefined: "drop", drop: "keep", keep: undefined};

function render() {
  const colors = baseColors.slice();
  const drop = [], keep = [];
  let dropTok = 0;
  for (const [i, st] of Object.entries(state)) {
    const desc = `[${tr.parents[i].split("/").pop()}] ${baseLabels[i]}`;
    if (st === "drop") { colors[i] = "#555"; drop.push(desc); dropTok += tr.values[i]; }
    if (st === "keep") { colors[i] = "#f2c94c"; keep.push(desc); }
  }
  Plotly.restyle(gd, {"marker.colors": [colors]});
  const parts = [];
  if (drop.length) parts.push("요약에서 제외하거나 한 줄로만 언급: " + drop.join("; ") + ".");
  if (keep.length) parts.push("반드시 자세히 보존: " + keep.join("; ") + ".");
  const extra = document.getElementById("extra").value.trim();
  if (extra) parts.push(extra);
  document.getElementById("prompt").value = parts.length ? "/compact " + parts.join(" ") : "";
  document.getElementById("sum").textContent = `버림 ${drop.length}개 (~${dropTok.toLocaleString()} tokens) · 남김 ${keep.length}개`;
}

gd.on("plotly_treemapclick", (e) => {
  const i = e.points[0].pointNumber;
  if (!TOGGLABLE.includes(i)) return true;  // 기본 동작(확대/축소)
  state[i] = NEXT[state[i]];
  if (!state[i]) delete state[i];
  render();
  return false;
});
document.getElementById("extra").addEventListener("input", render);
document.getElementById("copy").onclick = () => navigator.clipboard.writeText(document.getElementById("prompt").value);
render();
</script>
"""


def build_figure(items, root):
    palette = px.colors.qualitative.Set2
    cats = list(dict.fromkeys(c for c, _, _ in items))
    cat_color = {c: palette[i % len(palette)] for i, c in enumerate(cats)}

    ids, labels, parents, values, colors = [root], [root], [""], [sum(n for _, _, n in items)], ["lightgrey"]
    for c in cats:
        ids.append(f"{root}/{c}"); labels.append(c); parents.append(root)
        values.append(sum(n for cc, _, n in items if cc == c)); colors.append(cat_color[c])
    togglable = []
    for k, (c, label, n) in enumerate(items):
        if c not in FIXED:
            togglable.append(len(ids))
        ids.append(f"{root}/{c}/{k}"); labels.append(label); parents.append(f"{root}/{c}")
        values.append(n); colors.append(cat_color[c])

    fig = go.Figure(go.Treemap(
        ids=ids, labels=labels, parents=parents, values=values, branchvalues="total",
        marker=dict(colors=colors), textinfo="label+value+percent root",
    ))
    fig.update_layout(margin=dict(t=30, l=5, r=5, b=5), height=650)
    return fig, togglable


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("session", type=Path)
    ap.add_argument("-o", "--out", default="context.html")
    ap.add_argument("-w", "--window", type=int, default=200_000, help="모델 컨텍스트 창 크기 (1M 모델이면 1000000)")
    args = ap.parse_args()

    items, total = parse_session(args.session)
    free = args.window - total
    if free > 0:
        items.append(("Free space", "남은 공간", free))
    root = f"{args.session.stem[:8]} — {total:,} / {args.window:,} tokens ({total / args.window:.0%} 사용)"

    fig, togglable = build_figure(items, root)
    plot = fig.to_html(full_html=False, include_plotlyjs=True, div_id="tm")
    html = (f'<html><head><meta charset="utf-8"><title>Context Viewer</title></head><body>'
            f'{plot}<script>const TOGGLABLE = {json.dumps(togglable)};</script>{PANEL}</body></html>')
    Path(args.out).write_text(html, encoding="utf-8")
    print(f"{args.out} 저장 ({total:,} / {args.window:,} tokens, {total / args.window:.0%} 사용)")


if __name__ == "__main__":
    main()
