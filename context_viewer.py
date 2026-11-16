"""Claude Code 세션 1개의 컨텍스트 구성을 트리맵(HTML)으로 시각화하는 MVP.

사용법:
    pip install plotly
    python context_viewer.py ~/.claude/projects/<프로젝트>/<세션ID>.jsonl -o context.html
"""
import argparse
import json
from pathlib import Path

import plotly.express as px


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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("session", type=Path)
    ap.add_argument("-o", "--out", default="context.html")
    args = ap.parse_args()

    items, total = parse_session(args.session)
    root = f"{args.session.stem[:8]} (총 {total:,} tokens)"
    fig = px.treemap(
        names=None,
        path=[[root] * len(items), [c for c, _, _ in items], [l for _, l, _ in items]],
        values=[n for _, _, n in items],
    )
    fig.update_traces(textinfo="label+value+percent root")
    fig.update_layout(margin=dict(t=30, l=5, r=5, b=5))
    fig.write_html(args.out)
    print(f"{args.out} 저장 (항목 {len(items)}개, 총 {total:,} tokens)")


if __name__ == "__main__":
    main()
