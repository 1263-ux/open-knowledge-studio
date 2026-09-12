# -*- coding: utf-8 -*-
"""Diagram generator v2 - proper visual design for the OKS docs site."""
import html
import io
import os

FONT = "-apple-system, 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', sans-serif"
MONO = "'JetBrains Mono', Consolas, Menlo, monospace"

DEFS = """<defs>
  <filter id="sh" x="-20%" y="-20%" width="140%" height="140%">
    <feDropShadow dx="0" dy="2" stdDeviation="3" flood-color="#0f172a" flood-opacity="0.08"/>
  </filter>
  <linearGradient id="gblue" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0" stop-color="#3b82f6"/><stop offset="1" stop-color="#1d4ed8"/>
  </linearGradient>
  <linearGradient id="gviolet" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0" stop-color="#8b5cf6"/><stop offset="1" stop-color="#6d28d9"/>
  </linearGradient>
  <linearGradient id="gamber" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0" stop-color="#f59e0b"/><stop offset="1" stop-color="#d97706"/>
  </linearGradient>
  <marker id="ar" markerWidth="9" markerHeight="9" refX="8" refY="4.5" orient="auto">
    <path d="M0,0 L9,4.5 L0,9 z" fill="#2563eb"/>
  </marker>
</defs>"""


def text(x, y, s, size=13, fill="#334155", weight="normal", anchor="middle", mono=False):
    f = MONO if mono else FONT
    return (f'<text x="{x}" y="{y}" text-anchor="{anchor}" fill="{fill}" '
            f'font-size="{size}" font-weight="{weight}" font-family="{f}">{html.escape(s)}</text>')


def badge(x, y, n, color="#2563eb"):
    return (f'<circle cx="{x}" cy="{y}" r="11" fill="{color}"/>'
            f'<text x="{x}" y="{y+4}" text-anchor="middle" fill="#ffffff" font-size="12" '
            f'font-weight="700" font-family="{FONT}">{n}</text>')


def card(x, y, w, h, title, subs, grad="gblue", title_size=15.5, badge_n=None):
    p = ['<g filter="url(#sh)">',
         f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="12" fill="#ffffff" stroke="#e2e8f0"/>',
         f'<rect x="{x}" y="{y}" width="{w}" height="42" rx="12" fill="url(#{grad})"/>',
         f'<rect x="{x}" y="{y+30}" width="{w}" height="12" fill="url(#{grad})"/>']
    tx = x + w / 2
    if badge_n:
        p.append(badge(x + 24, y + 21, badge_n))
        tx = x + 12 + (w - 24) / 2
    p.append(text(tx, y + 27, title, size=title_size, fill="#ffffff", weight="700"))
    ly = y + 64
    for line in subs:
        p.append(text(x + w / 2, ly, line, size=12.3, fill="#64748b"))
        ly += 17
    p.append('</g>')
    return "\n".join(p)


def harrow(x1, x2, y):
    return (f'<line x1="{x1}" y1="{y}" x2="{x2}" y2="{y}" stroke="#2563eb" '
            f'stroke-width="2.5" marker-end="url(#ar)"/>')


def varrow(x, y1, y2, label=""):
    p = [f'<line x1="{x}" y1="{y1}" x2="{x}" y2="{y2-3}" stroke="#2563eb" '
         f'stroke-width="2.5" marker-end="url(#ar)"/>']
    if label:
        p.append(text(x + 10, (y1 + y2) / 2 + 4, label, size=11.5, fill="#2563eb", anchor="start"))
    return "\n".join(p)


def wrap(out_name, body, w, h):
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
           f'viewBox="0 0 {w} {h}" font-family="{FONT}">{DEFS}\n{body}\n</svg>')
    io.open(out_name, "w", encoding="utf-8").write(svg)
    print(out_name, f"{w}x{h}")


os.makedirs("docs/assets/diagrams", exist_ok=True)

# ============ 1. knowledge-pipeline: S-flow two rows, 7 stages ============
W, H, CW, CH, G = 1080, 330, 220, 92, 42
row1_y, row2_y = 34, 176


def sx(i):
    return 26 + i * (CW + G)


b1 = []
titles = [
    ("来源", "文章/视频/文件/网页", "人提供或授权采集"),
    ("证据片段", "Provider 机械提取", "只换格式不换知识"),
    ("清单 Manifest", "完整性校验 + 指纹", "可回溯到 locator"),
    ("Raw Bundle", "raw-commit 落盘", "raw/{YYYY}/{MM}/{DD}/"),
    ("Candidate", "Agent 提议 → drafts/", "带来源与缺口"),
    ("人审", "接受 / 修改 / 拒绝", "唯一的晋升门"),
    ("Wiki", "已审核长期知识", "进入召回与衰减"),
]
grads = ["gblue", "gblue", "gblue", "gblue", "gviolet", "gamber", "gblue"]
for i, (t, s1, s2) in enumerate(titles[:4]):
    b1.append(card(sx(i), row1_y, CW, CH, t, [s1, s2], badge_n=i + 1, grad=grads[i]))
for i, (t, s1, s2) in enumerate(titles[4:]):
    x = sx(3 - i)
    b1.append(card(x, row2_y, CW, CH, t, [s1, s2], badge_n=i + 5, grad=grads[i + 4]))
for i in range(3):
    b1.append(harrow(sx(i) + CW + 3, sx(i + 1) - 4, row1_y + CH / 2))
elbow_x = sx(3) + CW / 2
b1.append(f'<path d="M {elbow_x} {row1_y+CH+3} L {elbow_x} {row2_y-6}" fill="none" '
          f'stroke="#2563eb" stroke-width="2.5" marker-end="url(#ar)"/>')
for i in range(3):
    x_right = sx(3 - i)
    x_left = sx(2 - i)
    b1.append(f'<line x1="{x_right - 3}" y1="{row2_y + CH/2}" x2="{x_left + CW + 5}" '
              f'y2="{row2_y + CH/2}" stroke="#2563eb" stroke-width="2.5" marker-end="url(#ar)"/>')
b1.append(text(W / 2, H - 14, "Agent 可以提出知识，但不能批准自己的 Candidate —— 每条长期记忆都经过人审（宪法 A1 / P9）",
               size=12.5, fill="#94a3b8"))
wrap("docs/assets/diagrams/knowledge-pipeline.svg", "\n".join(b1), W, H)

# ============ 2. triple-layer: vertical architecture bands ============
W, H = 1080, 390
BX, BW = 250, 660
b2 = ['<rect width="100%" height="100%" rx="14" fill="#f8fafc"/>',
      f'<rect x="{BX+BW/2-100}" y="16" width="200" height="38" rx="19" fill="#0f172a"/>',
      text(BX + BW / 2, 40, 'oks recall "<query>"', size=14.5, fill="#ffffff", mono=True),
      varrow(BX + BW / 2, 54, 84)]
layers = [
    ("检索层 · Node-BM25", "gblue",
     "SQLite FTS5 按 ## 标题节点索引 · title 5x > tags 3x > body 1x",
     "决定「哪些命中」", "abstract 随索引，检索零文件读取", 90),
    ("注入层 · Soul Boost", "gviolet",
     "type boost (anti-pattern x1.5) · review bonus · generic demotion",
     "决定「哪些到达 Agent」", "失败教训排在泛化概念前面", 174),
    ("衰减层 · Memory Curve", "gamber",
     "importance x e^(-λ·days) + ln(1+access) + pin · hot→warm→cold",
     "决定「多旧还值得出现」", "类型化 λ，使用次数只影响排序 (P9)", 258),
]
for i, (name, grad, f1, verdict, note, y) in enumerate(layers):
    b2.append(f'<g filter="url(#sh)"><rect x="{BX}" y="{y}" width="{BW}" height="66" rx="12" '
              f'fill="#ffffff" stroke="#e2e8f0"/>'
              f'<rect x="{BX}" y="{y}" width="8" height="66" rx="4" fill="url(#{grad})"/></g>')
    b2.append(text(BX + 26, y + 27, name, size=16, fill="#0f172a", weight="700", anchor="start"))
    b2.append(text(BX + 26, y + 49, f1, size=11.6, fill="#64748b", anchor="start", mono=True))
    b2.append(text(BX + BW - 20, y + 27, verdict, size=13, fill="#1d4ed8", weight="600", anchor="end"))
    b2.append(text(BX + BW + 22, y + 34, note, size=11.5, fill="#94a3b8", anchor="start"))
    if i < 2:
        b2.append(varrow(BX + BW / 2, y + 66, y + 84))
b2.append(varrow(BX + BW / 2, 324, 354, "L0–L3 预算降级注入，带来源标签"))
wrap("docs/assets/diagrams/triple-layer-recall.svg", "\n".join(b2), W, H)

# ============ 3. mail-model: Thread spine + three satellites ============
W, H = 1080, 330
b3 = ['<rect width="100%" height="100%" rx="14" fill="#f8fafc"/>']
b3.append(f'<g filter="url(#sh)"><rect x="{W/2-115}" y="112" width="230" height="104" rx="14" fill="#0f172a"/>'
          f'<rect x="{W/2-115}" y="112" width="230" height="46" rx="14" fill="#1e293b"/>'
          f'<rect x="{W/2-115}" y="142" width="230" height="16" fill="#1e293b"/></g>')
b3.append(text(W / 2, 142, "Thread", size=18, fill="#ffffff", weight="700"))
b3.append(text(W / 2, 172, "有主题边界的持久通信上下文", size=12, fill="#94a3b8"))
b3.append(text(W / 2, 196, "跨 Session / Agent / 机器继续", size=12, fill="#94a3b8"))
sat = [
    ("Message", "意图 + 证据 + 验收标准", "delegate 自动装配 handoff 字段", "gblue", 70, 36),
    ("Session Receipt", "每 Session 独立投递记录", "可重建投影，不是已读回执", "gviolet", 70, 206),
    ("Host Adapter", "Claude / Codex / DSH / Pi", "同一 Mail Core，CLI 是核心入口", "gamber", 710, 121),
]
for t, s1, s2, grad, x, y in sat:
    b3.append(card(x, y, 300, 104, t, [s1, s2], grad=grad, title_size=15))
b3.append(harrow(374, W / 2 - 122, 88))
b3.append(harrow(374, W / 2 - 122, 258))
b3.append(f'<line x1="{W/2+120}" y1="164" x2="{W-336}" y2="164" stroke="#2563eb" '
          f'stroke-width="2.5" marker-end="url(#ar)"/>')
b3.append(text(W / 2, 310, "Mail 是协调与评审证据，不是可召回知识 —— 不参与 Recall，不衰减（宪法 A1）",
               size=12.5, fill="#94a3b8"))
wrap("docs/assets/diagrams/mail-model.svg", "\n".join(b3), W, H)
