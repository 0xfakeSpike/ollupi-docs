"""Figures for 《AI 时代到来，你的用户画像的价值会被谁赚走？》.

Built to be read on a phone and shared on their own on X: 16:9 (1600x900), one point per figure, the title states
that point, big type (title 56px, nothing under 22px), an icon or a big number carries each figure, and no more
than a few dozen words. The footer gives the figure number and the source.

Each party has one fixed color in every figure: platforms = teal, AI companies = indigo, your personal agent = pink,
the model itself = slate. In charts, an earlier period is light indigo and a later one is indigo.

Run: python3 scripts/figures/user-profile.py zh   (en once the English article exists)
Output: docs/{zh,en}/articles/04-user-profile/fig-*.svg, next to the article that uses them, plus the share card
(scripts/figures/user-profile-og.svg, exported to docs/public/og/user-profile.png) and the X cover
(scripts/figures/user-profile-cover.svg, 5:2). Commit the output. Regenerate both cards in English once the English
article exists, since the site's root URL is English.
"""
import glob
import os
import sys

LANG = sys.argv[1] if len(sys.argv) > 1 else "zh"
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, "docs", LANG, "articles", "04-user-profile")
W, H, PAD = 1600, 900, 80

INDIGO, INDIGO_2, INDIGO_DEEP, TINT = "#4f46e5", "#818cf8", "#1e1b4b", "#eef2ff"
TEAL, TEAL_TINT = "#0d9488", "#f0fdfa"
PINK, PINK_TINT = "#ec4899", "#fdf2f8"
SLATE, SLATE_TINT = "#64748b", "#f1f5f9"
ROSE = "#f43f5e"
INK2, MUTED, FAINT, RULE, BASE = "#334155", "#64748b", "#94a3b8", "#e2e8f0", "#cbd5e1"
FONT = ('-apple-system, BlinkMacSystemFont, "PingFang SC", "Hiragino Sans GB", "Noto Sans CJK SC", '
        '"Microsoft YaHei", "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif')


def t(zh, en):
    return zh if LANG == "zh" else en


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


SIZES = {"t": 56, "k": 44, "n": 88, "m": 34, "b": 30, "s": 26, "f": 22}


def tw(s, size):
    """Approximate rendered width: CJK and full-width glyphs are 1em, the rest about 0.58em."""
    return sum(size if ord(c) > 0x2E80 else size * 0.58 for c in s)


def wrap_lines(s, size, maxw):
    """Split on spaces so each line fits maxw. Chinese has no spaces and stays on one line."""
    if tw(s, size) <= maxw or " " not in s:
        return [s]
    lines, cur = [], ""
    for w in s.split(" "):
        cand = f"{cur} {w}" if cur else w
        if cur and tw(cand, size) > maxw:
            lines.append(cur)
            cur = w
        else:
            cur = cand
    return lines + [cur]


class Fig:
    def __init__(self, n, title, source=""):
        foot = t(f"图 {n}", f"Fig. {n}") + (f" · {source}" if source else "")
        self.p = [
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}">',
            "<defs>" + "".join(
                f'<marker id="{mid}" viewBox="0 0 10 10" refX="8" refY="5" markerUnits="userSpaceOnUse" '
                f'markerWidth="26" markerHeight="26" orient="auto-start-reverse"><path d="M0,1 L9,5 L0,9 z" '
                f'fill="{c}"/></marker>'
                for mid, c in (("aS", SLATE), ("aI", INDIGO), ("aR", ROSE), ("aT", TEAL), ("aP", PINK))) + "</defs>",
            f"<style>text {{ font-family: {FONT}; fill: {INDIGO_DEEP}; }}"
            f" .t {{ font-size: 56px; font-weight: 800; }}"
            f" .k {{ font-size: 44px; font-weight: 800; }}"
            f" .n {{ font-size: 88px; font-weight: 800; }}"
            f" .m {{ font-size: 34px; font-weight: 700; }}"
            f" .b {{ font-size: 30px; fill: {INK2}; }}"
            f" .s {{ font-size: 26px; fill: {MUTED}; }}"
            f" .f {{ font-size: 22px; fill: {FAINT}; }}</style>",
            f'<rect width="{W}" height="{H}" fill="#ffffff"/>',
            f'<text class="t" x="{PAD}" y="118" style="font-size:{min(56, (W - 2 * PAD) / tw(title, 1)):.1f}px">'
            f'{esc(title)}</text>',
            f'<text class="f" x="{PAD}" y="{H - 36}">{esc(foot)}</text>',
            f'<text class="f" x="{W - PAD}" y="{H - 36}" text-anchor="end">'
            f'{esc(t("AI 时代到来，你的用户画像的价值会被谁赚走？", "AI Knows You Better Than Ever. Who Gets Paid for It?"))}</text>',
        ]

    def add(self, s):
        self.p.append(s)

    def text(self, x, y, s, cls, anchor="start", fill=None, rotate=None, maxw=None):
        """maxw: shrink the font so the line fits."""
        styles = [f"fill:{fill}"] if fill else []
        if maxw and tw(s, SIZES[cls]) > maxw:
            styles.append(f"font-size:{SIZES[cls] * maxw / tw(s, SIZES[cls]):.1f}px")
        st = f' style="{";".join(styles)}"' if styles else ""
        tr = f' transform="rotate({rotate} {x} {y})"' if rotate is not None else ""
        self.add(f'<text class="{cls}" x="{x:.1f}" y="{y:.1f}" text-anchor="{anchor}"{st}{tr}>{esc(s)}</text>')

    def wrap(self, x, y, s, cls, maxw, lh=None, anchor="start", fill=None):
        """Draw s wrapped to maxw (English only), first baseline at y. Returns the y below the last line."""
        size = SIZES[cls]
        lh = lh or size * 1.2
        lines = wrap_lines(s, size, maxw)
        for i, ln in enumerate(lines):
            self.text(x, y + i * lh, ln, cls, anchor, fill, maxw=maxw)
        return y + len(lines) * lh

    def rect(self, x, y, w, h, fill, stroke="none", r=16, sw=3, dash=False):
        d = ' stroke-dasharray="12 9"' if dash else ""
        self.add(f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="{r}" fill="{fill}" '
                 f'stroke="{stroke}" stroke-width="{sw}"{d}/>')

    def arrow(self, d, mid="aS", color=SLATE, sw=5, dash=False):
        st = ' stroke-dasharray="14 10"' if dash else ""
        self.add(f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{sw}" stroke-linecap="round" '
                 f'marker-end="url(#{mid})"{st}/>')

    def bar(self, x, base, w, h, fill):
        """A vertical bar anchored to the baseline, rounded at the data end."""
        r = min(8, h / 2, w / 2)
        top = base - h
        self.add(f'<path d="M{x:.1f},{base:.1f} V{top + r:.1f} Q{x:.1f},{top:.1f} {x + r:.1f},{top:.1f} '
                 f'H{x + w - r:.1f} Q{x + w:.1f},{top:.1f} {x + w:.1f},{top + r:.1f} V{base:.1f} Z" fill="{fill}"/>')

    def mark(self, cx, cy, ok, r=24):
        """A ✓ / ✕ disc."""
        self.add(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{INDIGO if ok else ROSE}"/>')
        k = r / 12
        if ok:
            self.add(f'<path d="M{cx - 5 * k},{cy} L{cx - 1.5 * k},{cy + 4 * k} L{cx + 5.5 * k},{cy - 4 * k}" '
                     f'fill="none" stroke="#fff" stroke-width="{2.6 * k}" stroke-linecap="round" stroke-linejoin="round"/>')
        else:
            self.add(f'<path d="M{cx - 4.5 * k},{cy - 4.5 * k} L{cx + 4.5 * k},{cy + 4.5 * k} M{cx + 4.5 * k},'
                     f'{cy - 4.5 * k} L{cx - 4.5 * k},{cy + 4.5 * k}" stroke="#fff" stroke-width="{2.6 * k}" '
                     f'stroke-linecap="round"/>')

    def save(self, name):
        path = os.path.join(OUT, name + ".svg")
        with open(path, "w") as f:
            f.write("\n".join(self.p + ["</svg>"]) + "\n")
        return path


# ---- icons, centered on (cx, cy), about 120px at s=1 ----

def icon_person(f, cx, cy, c, s=1.0):
    f.add(f'<circle cx="{cx}" cy="{cy - 34 * s}" r="{30 * s}" fill="{c}"/>')
    f.add(f'<path d="M{cx - 58 * s},{cy + 62 * s} Q{cx - 58 * s},{cy + 6 * s} {cx},{cy + 6 * s} '
          f'Q{cx + 58 * s},{cy + 6 * s} {cx + 58 * s},{cy + 62 * s} Z" fill="{c}"/>')


def icon_crowd(f, cx, cy, c):
    for dx, s in ((-46, 0.6), (46, 0.6), (0, 0.75)):
        icon_person(f, cx + dx, cy + (8 if s < 0.7 else 0), c, s)


def icon_store(f, cx, cy, c):
    f.add(f'<rect x="{cx - 52}" y="{cy - 10}" width="104" height="66" rx="6" fill="{c}"/>')
    f.add(f'<path d="M{cx - 62},{cy - 10} L{cx - 50},{cy - 50} H{cx + 50} L{cx + 62},{cy - 10} Z" fill="{c}"/>')
    f.add(f'<rect x="{cx - 16}" y="{cy + 18}" width="32" height="38" rx="4" fill="#ffffff"/>')


def icon_bubble(f, cx, cy, c):
    f.add(f'<rect x="{cx - 62}" y="{cy - 48}" width="124" height="84" rx="22" fill="{c}"/>')
    f.add(f'<path d="M{cx - 30},{cy + 34} L{cx - 40},{cy + 62} L{cx - 4},{cy + 34} Z" fill="{c}"/>')
    for dx in (-30, 0, 30):
        f.add(f'<circle cx="{cx + dx}" cy="{cy - 6}" r="8" fill="#ffffff"/>')


def icon_phone(f, cx, cy, c):
    f.add(f'<rect x="{cx - 38}" y="{cy - 62}" width="76" height="124" rx="16" fill="{c}"/>')
    f.add(f'<rect x="{cx - 28}" y="{cy - 48}" width="56" height="88" rx="6" fill="#ffffff"/>')
    f.add(f'<circle cx="{cx}" cy="{cy - 18}" r="11" fill="{c}"/>')
    f.add(f'<path d="M{cx - 18},{cy + 22} Q{cx},{cy - 2} {cx + 18},{cy + 22} Z" fill="{c}"/>')


def icon_chip(f, cx, cy, c):
    for i in (-1, 0, 1):
        for x1, y1, x2, y2 in ((cx + i * 22, cy - 62, cx + i * 22, cy - 44), (cx + i * 22, cy + 44, cx + i * 22, cy + 62),
                               (cx - 62, cy + i * 22, cx - 44, cy + i * 22), (cx + 44, cy + i * 22, cx + 62, cy + i * 22)):
            f.add(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{c}" stroke-width="8" stroke-linecap="round"/>')
    f.add(f'<rect x="{cx - 46}" y="{cy - 46}" width="92" height="92" rx="14" fill="{c}"/>')
    f.add(f'<rect x="{cx - 22}" y="{cy - 22}" width="44" height="44" rx="6" fill="#ffffff"/>')


# ---------------------------------------------------------------------------

def fig_copies():
    f = Fig(1, t("你的画像，现在有三份", "Your profile now exists in three copies"),
            t("Google、阿里、字节既有你的购物记录，也有你的聊天记录", "Google, Alibaba and ByteDance hold both your purchases and your chats"))
    pcx, pcy = W / 2, 250
    icon_person(f, pcx, pcy, INK2)
    f.text(pcx + 90, pcy + 20, t("你", "You"), "k")
    cards = [
        (TEAL, TEAL_TINT, icon_store, t("平台", "Platforms"), t("你买过什么", "What you bought"),
         t("淘宝 · Amazon · 抖音", "Taobao, Amazon")),
        (INDIGO, TINT, icon_bubble, t("大模型公司", "AI companies"), t("你说过什么", "What you said"),
         t("ChatGPT · 豆包", "ChatGPT, Doubao")),
        (PINK, PINK_TINT, icon_phone, t("你的个人 agent", "Personal agent"), t("你是谁、要什么", "Who you are, what you want"),
         t("存在你的设备上", "On your device")),
    ]
    cw, gap, top = 448, 48, 450
    for i, (c, tint, icon, who, what, ex) in enumerate(cards):
        x = PAD + i * (cw + gap)
        cx = x + cw / 2
        f.add(f'<path d="M{pcx},{pcy + 70} C{pcx},{top - 60} {cx},{pcy + 110} {cx},{top - 4}" fill="none" '
              f'stroke="{c}" stroke-width="5" stroke-dasharray="2 12" stroke-linecap="round"/>')
        f.rect(x, top, cw, 340, tint, c)
        icon(f, x + 100, top + 110, c)
        f.text(x + 190, top + 96, who, "m", maxw=cw - 210)
        f.text(x + 190, top + 140, ex, "s", maxw=cw - 210)
        f.text(x + 40, top + 214, t("它知道", "It knows"), "s")
        f.wrap(x + 40, top + 270, what, "k", cw - 80, lh=50, fill=c)
    return f.save("fig-1-copies")


def fig_unbundle():
    f = Fig(2, t("推荐要三样东西，大模型把它们拆开了", "LLMs split up the three things recommendation needs"),
            t("推荐可以由你的个人 agent 来做", "So your personal agent can do the recommending"))
    f.text(PAD, 214, t("以前：都在平台手里", "Before: all at the platform"), "m")
    f.rect(PAD, 240, 640, 520, TEAL_TINT, TEAL)
    items = [(icon_crowd, t("行为规律", "Patterns")), (icon_person, t("用户画像", "Your profile")),
             (icon_store, t("商品和内容", "Products"))]
    for i, (icon, lbl) in enumerate(items):
        cx = PAD + 110 + i * 210
        icon(f, cx, 450, TEAL)
        f.text(cx, 590, lbl, "m", "middle")
    f.text(PAD + 320, 700, t("平台", "The platform"), "k", "middle", fill=TEAL)
    f.arrow("M760,500 H860", "aS", SLATE, sw=6)
    x0 = 900
    f.text(x0, 214, t("现在：分在三处", "Now: in three places"), "m")
    rows = [(SLATE, SLATE_TINT, icon_chip, t("大模型", "The LLM"), t("装着行为规律，谁都能用", "Holds the patterns, open to anyone")),
            (PINK, PINK_TINT, icon_phone, t("你的个人 agent", "Your personal agent"), t("用户画像存在你的设备上", "Keeps your profile on your device")),
            (TEAL, TEAL_TINT, icon_store, t("平台", "The platform"), t("只剩商品和内容", "Only the products are left"))]
    for i, (c, tint, icon, name, what) in enumerate(rows):
        y = 240 + i * 180
        f.rect(x0, y, 620, 160, tint, c)
        icon(f, x0 + 90, y + 80, c)
        f.text(x0 + 180, y + 66, name, "m", maxw=420)
        f.wrap(x0 + 180, y + 110, what, "b", 420, lh=36)
    return f.save("fig-2-unbundle")


def fig_token():
    f = Fig(4, t("token 单价降了一半多，用量涨了 25 倍", "Tokens got 57% cheaper; usage grew 25×"),
            t("OpenRouter 2026 年 1 月与 10 月数据", "OpenRouter, January vs October 2026"))
    base, ph = 740, 400
    panels = [
        (PAD, t("每百万 token 的平均价格（闭源模型）", "Avg price per 1M tokens (closed)"),
         [(t("1 月", "Jan"), 1.21, "$1.21"), (t("10 月", "Oct"), 0.52, "$0.52")], 1.21),
        (860, t("每月用掉的 token", "Tokens used per month"),
         [(t("1 月", "Jan"), 31.6, t("约 32 万亿", "~32T")), (t("10 月", "Oct"), 790, t("790 万亿", "790T"))], 790),
    ]
    for x, title, bars, vmax in panels:
        f.wrap(x, 214, title, "m", 660, lh=40)
        f.add(f'<line x1="{x}" y1="{base}" x2="{x + 660}" y2="{base}" stroke="{BASE}" stroke-width="3"/>')
        for i, (lbl, v, vs) in enumerate(bars):
            bx = x + 60 + i * 260
            h = max(ph * v / vmax, 6)
            f.bar(bx, base, 180, h, INDIGO_2 if i == 0 else INDIGO)
            f.text(bx + 90, base - h - 22, vs, "m", "middle")
            f.text(bx + 90, base + 50, lbl, "b", "middle")
    f.text(PAD + 640, 330, "−57%", "n", "end", fill=INDIGO)
    f.text(860 + 20, 330, "×25", "n", "start", fill=INDIGO)
    f.text(860 + 20, 384, t("其中 76% 是 agent 用掉的", "76% of it used by agents"), "s")
    return f.save("fig-4-token")


def fig_parties():
    f = Fig(5, t("token 越便宜，大模型公司、平台、个人 agent 各有打算", "Cheaper tokens: what AI companies, platforms and agents do"),
            t("推断；2026 年已经发生的例子见正文", "Inference; 2026 examples in the text"))
    f.rect(W / 2 - 300, 180, 600, 110, SLATE_TINT, SLATE, r=55)
    f.text(W / 2, 250, t("token 越来越便宜", "Tokens keep getting cheaper"), "k", "middle", maxw=540)
    cards = [
        (INDIGO, TINT, "aI", icon_bubble, t("大模型公司", "AI companies"), t("转向手里的", "Lean on"),
         t("用户画像", "your profile")),
        (TEAL, TEAL_TINT, "aT", icon_store, t("平台", "Platforms"), t("用更好的 AI", "Use better AI"),
         t("把你留住", "to keep you")),
        (PINK, PINK_TINT, "aP", icon_phone, t("你的个人 agent", "Personal agent"), t("能做的事", "Can do more"),
         t("越来越多", "and more")),
    ]
    cw, gap, top = 448, 48, 430
    for i, (c, tint, mid, icon, who, l1, l2) in enumerate(cards):
        x = PAD + i * (cw + gap)
        cx = x + cw / 2
        sx = W / 2 + (i - 1) * 120
        f.arrow(f"M{sx},294 C{sx},360 {cx},340 {cx},{top - 14}", mid, c, sw=5)
        f.rect(x, top, cw, 340, tint, c)
        icon(f, x + 100, top + 100, c)
        f.text(x + 190, top + 112, who, "m", maxw=cw - 210)
        f.text(x + 40, top + 236, l1, "k", fill=c, maxw=cw - 80)
        f.text(x + 40, top + 296, l2, "k", fill=c, maxw=cw - 80)
    return f.save("fig-5-parties")


def fig_ads():
    f = Fig(6, t("ChatGPT 广告的下单率，只有搜索广告的三分之一", "ChatGPT ads convert at a third of the rate of search ads"),
            t("Kaiser 和 Schulze 工作论文（评审中）· 美国付费点击 · 2026", "Kaiser & Schulze working paper (under review) · US paid clicks · 2026"))
    x0, top, bw_max = PAD, 230, 560
    rows = [(t("ChatGPT 广告", "ChatGPT ads"), 0.37, INDIGO), (t("Google 搜索广告", "Google search ads"), 1.17, TEAL)]
    for i, (name, v, c) in enumerate(rows):
        y = top + i * 230
        f.text(x0, y + 40, name, "m")
        w = bw_max * v / 1.17
        f.rect(x0, y + 66, w, 96, c, r=10)
        f.text(x0 + w + 24, y + 150, f"{v}%", "n")
    f.text(x0, top + 500, t("点广告进来的人里，下单的比例", "Share of ad visitors who bought"), "s")
    rx, ry, s, g, per = 1040, 250, 40, 8, 10
    for k in range(87):
        r, c = divmod(k, per)
        f.rect(rx + c * (s + g), ry + r * (s + g), s, s, INDIGO if k >= 73 else RULE, r=8, sw=0)
    f.text(rx, ry - 30, t("同时投两边的 87 家广告主", "87 advertisers buying both"), "m", maxw=W - PAD - rx)
    f.text(rx, ry + 9 * (s + g) + 52, t("73 家在 ChatGPT 上一单没成交", "73 made no sale on ChatGPT"), "b")
    f.text(rx, ry + 9 * (s + g) + 96, t("成交全部来自另外 14 家", "All sales came from the other 14"), "s")
    return f.save("fig-6-ads")


def phone_frame(f, cx, top, w=300, h=380):
    x = cx - w / 2
    f.rect(x, top, w, h, "#ffffff", INK2, r=36, sw=4)
    f.rect(cx - 40, top + 16, 80, 10, BASE, r=5, sw=0)
    return x + 24, top + 48, w - 48


def fig_decision():
    f = Fig(7, t("广告离你下单越近，越值钱", "The closer an ad is to your purchase, the more it’s worth"),
            t("ChatGPT 广告 2026 年 2 月上线；Google 5 月宣布；抖音这笔服务费 8 月起收", "ChatGPT ads since Feb 2026; Google announced in May; Douyin’s fee since August"))
    centers, top = (330, 800, 1270), 160

    def ad_box(x, y, w, h, label):
        f.rect(x, y, w, h, TINT, INDIGO, r=12, dash=True)
        f.text(x + w / 2, y + h / 2 + 12, label, "m", "middle", fill=INDIGO, maxw=w - 24)

    def item(x, y, w, h, label):
        f.rect(x, y, w, h, "#ffffff", BASE, r=12)
        f.text(x + w / 2, y + h / 2 + 10, label, "b", "middle")

    # 1: an ad under the answer
    x, y, w = phone_frame(f, centers[0], top)
    f.text(x, y + 22, t("AI 的回答", "AI’s answer"), "s")
    for j, ww in enumerate((1.0, 0.85, 0.95, 0.7)):
        f.rect(x, y + 50 + j * 30, w * ww, 14, RULE, r=7, sw=0)
    ad_box(x, y + 210, w, 84, t("广告", "Ad"))
    # 2: an ad inside the list of picks
    x, y, w = phone_frame(f, centers[1], top)
    f.text(x, y + 22, t("AI 的推荐", "AI’s picks"), "s")
    item(x, y + 44, w, 72, t("推荐 1", "Pick 1"))
    ad_box(x, y + 132, w, 72, t("广告", "Ad"))
    item(x, y + 220, w, 72, t("推荐 2", "Pick 2"))
    # 3: no ad; a cut after you buy
    x, y, w = phone_frame(f, centers[2], top)
    f.text(x, y + 22, t("AI 的推荐", "AI’s pick"), "s")
    item(x, y + 44, w, 72, t("推荐 1", "Pick 1"))
    f.mark(x + 40, y + 160, True, r=22)
    f.text(x + 76, y + 171, t("你下单了", "You bought it"), "m", maxw=w - 80)
    ad_box(x, y + 210, w, 84, t("商家付 12%", "Seller pays 12%"))
    labels = [(t("回答下面挂一条广告", "An ad under the answer"), t("ChatGPT", "ChatGPT")),
              (t("推荐里插一条广告", "An ad among the picks"), t("Google AI Mode", "Google AI Mode")),
              (t("不放广告，成交后抽成", "No ad; a cut of the sale"), t("经豆包去抖音订酒店", "Douyin hotels booked via Doubao"))]
    for cx, (a, b) in zip(centers, labels):
        f.text(cx, top + 440, a, "m", "middle", maxw=440)
        f.text(cx, top + 482, b, "s", "middle")
    f.arrow(f"M{PAD + 40},{top + 570} H{W - PAD - 40}", "aI", INDIGO, sw=6)
    lbl = t("越来越值钱，也越难分清哪条是广告", "Worth more, and harder to tell it’s an ad")
    lw = tw(lbl, 34) + 60
    f.rect(W / 2 - lw / 2, top + 542, lw, 56, "#ffffff", r=0, sw=0)
    f.text(W / 2, top + 582, lbl, "m", "middle")
    return f.save("fig-7-decision")


def fig_gate():
    f = Fig(8, t("AI 把你带来，平台欢迎；AI 替你下单，平台拦着", "AI that sends you in is welcome; AI that buys is blocked"),
            t("截至 2026 年 11 月", "As of November 2026"))
    px = 1180
    f.rect(px, 180, W - PAD - px, 620, TEAL_TINT, TEAL)
    icon_store(f, px + (W - PAD - px) / 2, 440, TEAL)
    f.text(px + (W - PAD - px) / 2, 580, t("平台", "Platform"), "k", "middle")
    door = px - 30
    f.add(f'<line x1="{door}" y1="470" x2="{door}" y2="800" stroke="{ROSE}" stroke-width="6" stroke-dasharray="14 10"/>')
    groups = [
        (t("只帮你挑，再把你带到平台", "Picks for you, then sends you to the platform"), True, 214, [
            (t("ChatGPT 广告", "ChatGPT ads"), t("Amazon 花钱买，把你带回 amazon.com", "Amazon pays it to send you back")),
            (t("豆包", "Doubao"), t("带你去抖音订酒店，商家付 12%", "Hotels pay Douyin a 12% fee"))]),
        (t("替你直接下单", "Buys for you directly"), False, 486, [
            (t("Perplexity Comet", "Perplexity Comet"), t("被 Amazon 起诉", "Sued by Amazon")),
            (t("豆包手机助手", "Doubao phone assistant"), t("151 款 App 不让它操作", "151 apps won’t let it in")),
            (t("ChatGPT 里直接下单", "Checkout inside ChatGPT"), t("商家不跟，3 月收缩", "Merchants balked; scaled back"))]),
    ]
    for head, ok, y, rows in groups:
        f.text(PAD, y, head, "s")
        for j, (name, what) in enumerate(rows):
            cy = y + 54 + j * 104
            f.text(PAD, cy, name, "m", maxw=470)
            f.text(PAD, cy + 40, what, "s", maxw=470)
            end = px - 12 if ok else door - 50
            f.arrow(f"M560,{cy} H{end}", "aI" if ok else "aR", INDIGO if ok else ROSE, sw=5, dash=not ok)
            f.mark(end - 60 if ok else door - 24, cy, ok)
    return f.save("fig-8-gate")


def fig_scenarios():
    f = Fig(9, t("平台开不开放权限、AI 贵不贵，决定了三种结局", "Will platforms let AI in? Will AI get cheap? Three outcomes"),
            t("推断；三种结局会在不同行业和地区同时出现", "Inference; the outcomes will coexist across industries and regions"))
    gx, gy, cw, ch, gap = 230, 180, 630, 250, 24
    cells = [
        (0, 0, INDIGO, TINT, t("不想看广告，就得付钱", "Pay to skip the ads"), t("免费的有广告，推荐还可能偏向给钱的商家", "Free AI shows ads; its picks may favor sellers who paid"), False),
        (1, 0, PINK, PINK_TINT, t("个人 agent 替你货比各家", "Your agent shops around for you"), t("能进各家平台，你的画像也能带走", "It can go into any platform; your profile moves with you"), False),
        (0, 1, TEAL, TEAL_TINT, t("每家平台只认自家的 AI", "Each platform lets in only its own AI"), t("外面的 AI 进不来，你只能在一家买", "Outside AI is kept out; you buy where your AI lives"), False),
        (1, 1, SLATE, "#ffffff", t("平台开放了，但 AI 太贵", "Open platforms, costly AI"), t("只有少数人用得起，多半只是过渡", "Only a few can afford it; likely a passing stage"), True),
    ]
    for cx, cy, c, tint, name, line, faint in cells:
        x, y = gx + cx * (cw + gap), gy + cy * (ch + gap)
        f.rect(x, y, cw, ch, tint, c, dash=faint)
        yb = f.wrap(x + 40, y + 76, name, "k", cw - 80, lh=50, fill=SLATE if faint else None)
        f.wrap(x + 40, yb + 18, line, "b", cw - 80, lh=36)
    ax_y = gy + 2 * ch + gap + 24
    f.add(f'<circle cx="{gx + 12}" cy="{ax_y + 35}" r="12" fill="{ROSE}"/>')
    f.text(gx + 36, ax_y + 44, t("国内现在更靠近左下角", "China is closer to the bottom left today"), "s", fill=ROSE)
    f.arrow(f"M{gx},{ax_y} H{gx + 2 * cw + gap}", "aS", SLATE, sw=4)
    f.text(gx + 2 * cw + gap, ax_y + 44, t("平台越向外部 AI 开放权限", "The more platforms let outside AI in"), "s", "end")
    ax_x = gx - 30
    f.arrow(f"M{ax_x},{gy + 2 * ch + gap} V{gy}", "aS", SLATE, sw=4)
    f.text(ax_x - 20, gy + ch + gap / 2, t("AI 用起来越便宜", "Cheaper AI"), "s", "middle", rotate=-90)
    return f.save("fig-9-scenarios")


def fig_twoways():
    f = Fig(3, t("同一家大模型公司，对你的数据有两种做法", "One AI company, two ways to treat your data"),
            t("依据：Anthropic 消费者条款更新（2025-08）；OpenAI API 数据政策", "Sources: Anthropic consumer terms (Aug 2025); OpenAI API data policy"))
    cols = [
        (INDIGO, TINT, icon_bubble, t("直接用 ChatGPT、Claude", "Using ChatGPT or Claude directly"),
         [t("聊天记录和画像都留在它那边", "Chats and profile stay with it"), t("可以拿去训练、挑广告", "Can be used for training and ads")],
         t("它手里有你完整的画像", "It holds your whole profile"), INDIGO),
        (PINK, PINK_TINT, icon_phone, t("你的个人 agent 调用 API", "Your personal agent calls the API"),
         [t("每次只发用得到的部分", "Sends only what each call needs"), t("默认不拿去训练", "Not used for training by default")],
         t("它只按用量收费", "It just charges by usage"), SLATE),
    ]
    cw, gap, top = 680, 80, 190
    for i, (c, tint, icon, head, lines, tag, tagc) in enumerate(cols):
        x = PAD + i * (cw + gap)
        f.rect(x, top, cw, 600, tint, c)
        icon(f, x + 100, top + 110, c)
        f.wrap(x + 190, top + 104, head, "m", cw - 220, lh=40)
        for j, ln in enumerate(lines):
            f.add(f'<circle cx="{x + 56}" cy="{top + 262 + j * 80}" r="9" fill="{c}"/>')
            f.text(x + 84, top + 274 + j * 80, ln, "b")
        f.rect(x + 40, top + 470, cw - 80, 88, tagc, r=44, sw=0)
        f.text(x + cw / 2, top + 528, tag, "m", "middle", fill="#ffffff")
    return f.save("fig-3-twoways")


def fig_users():
    f = Fig(10, t("AI 帮你挑，但你自己去付钱", "AI helps you choose; you still pay elsewhere"),
            t("Attentive 2026 年 8 月调查，3054 名美国成年人", "Attentive survey, August 2026, 3,054 US adults"))
    f.text(PAD, 380, "62%", "n", fill=INDIGO)
    f.text(PAD, 440, t("用 AI 帮忙购物的人里，", "of people who shopped with AI"), "b")
    f.text(PAD, 484, t("因为 AI 买了", "bought something other than"), "b")
    f.text(PAD, 528, t("和平时不同的东西", "their usual pick because of it"), "b")
    x0, bw = 700, 640
    f.text(x0, 214, t("最近一次 AI 帮忙的购买，在哪里付的钱", "Where they paid, last AI-assisted purchase"), "m", maxw=W - PAD - x0)
    rows = [(t("零售商或电商平台", "A retailer or marketplace"), 59, TEAL),
            (t("品牌官网", "The brand’s own site"), 31, SLATE),
            (t("聊天机器人里", "Inside the chatbot"), 10, INDIGO)]
    for i, (lbl, v, c) in enumerate(rows):
        y = 270 + i * 160
        f.text(x0, y + 30, lbl, "b")
        f.rect(x0, y + 50, bw * v / 59, 64, c, r=10, sw=0)
        f.text(x0 + bw * v / 59 + 20, y + 100, f"{v}%", "k")
    return f.save("fig-10-users")


class Card(Fig):
    """A bare canvas in the same style, for the share card and the X cover (no header or footer)."""

    def __init__(self, w, h):
        self.p = [
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}">',
            f"<style>text {{ font-family: {FONT}; fill: {INDIGO_DEEP}; }}"
            f" .t {{ font-size: 68px; font-weight: 800; }}"
            f" .m {{ font-size: 34px; font-weight: 700; }}"
            f" .s {{ font-size: 30px; fill: {MUTED}; }}</style>",
            f'<rect width="{w}" height="{h}" fill="#ffffff"/>',
        ]

    def save_to(self, path):
        with open(path, "w") as f:
            f.write("\n".join(self.p + ["</svg>"]) + "\n")
        return path


THREE = [(TEAL, icon_store, t("平台", "Platforms")), (INDIGO, icon_bubble, t("大模型公司", "AI companies")),
         (PINK, icon_phone, t("你的个人 agent", "Personal agent"))]


def three_icons(c, x0, step, y):
    for i, (col, icon, lbl) in enumerate(THREE):
        cx = x0 + i * step
        icon(c, cx, y, col)
        c.text(cx, y + 120, lbl, "m", "middle", maxw=step - 24)


def share_card():
    """1200x630 link preview; the site serves it from docs/public/og/user-profile.png."""
    c = Card(1200, 630)
    for i, ln in enumerate((t("AI 时代到来，", "AI knows you"), t("你的用户画像的价值", "better than ever."), t("会被谁赚走？", "Who gets paid for it?"))):
        c.text(80, 130 + i * 86, ln, "t")
    three_icons(c, 250, 350, 440)
    return c.save_to(os.path.join(ROOT, "scripts", "figures", "user-profile-og.svg"))


def x_cover():
    """1792x716 (5:2) cover for the X Article."""
    c = Card(1792, 716)
    for i, ln in enumerate((t("AI 时代到来，", "AI knows you"), t("你的用户画像的价值", "better than ever."), t("会被谁赚走？", "Who gets paid for it?"))):
        c.text(100, 220 + i * 90, ln, "t")
    c.text(100, 520, t("平台、大模型公司，还是你自己的个人 agent", "Platforms, AI companies, or your own personal agent"), "s")
    three_icons(c, 1080, 260, 320)
    return c.save_to(os.path.join(ROOT, "scripts", "figures", "user-profile-cover.svg"))


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    for old in glob.glob(os.path.join(OUT, "fig-*.svg")):
        os.remove(old)
    for fn in (fig_copies, fig_unbundle, fig_twoways, fig_token, fig_parties, fig_ads, fig_decision, fig_gate,
               fig_scenarios, fig_users, share_card, x_cover):
        print(fn())
