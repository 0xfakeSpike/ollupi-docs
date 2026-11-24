"""Figures for 《agent 需要一个池子》 (docs/{zh,en}/intro/why.md).

Same rules as scripts/figures/agent-eval.py: 16:9 (1600x900), one point per figure, the title states that point,
big type (title 56px, nothing under 22px), few words, a footer with the figure number and source.

Colors: Ollupi = indigo; the other approaches = slate; running = indigo, idle or waiting = light slate;
a bad outcome = rose, a good one = teal. Text never takes a series color except labels of a series.

Run: python3 scripts/figures/why.py zh   and   python3 scripts/figures/why.py en
Output: docs/{zh,en}/intro/why-fig-*.svg, next to the page that uses them. Commit the output.
Not under docs/public/images: scripts/sync.mjs replaces that folder with the engine repository's figures.
"""
import glob
import os
import sys

LANG = sys.argv[1] if len(sys.argv) > 1 else "zh"
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, "docs", LANG, "intro")
W, H, PAD = 1600, 900, 80

INDIGO, INDIGO_2, INDIGO_DEEP, TINT, LINE = "#4f46e5", "#818cf8", "#1e1b4b", "#eef2ff", "#c7d2fe"
TEAL, TEAL_TINT = "#0d9488", "#f0fdfa"
SLATE, SLATE_TINT, SLATE_2 = "#64748b", "#f1f5f9", "#cbd5e1"
ROSE, ROSE_TINT = "#e11d48", "#fff1f2"
INK2, MUTED, FAINT, RULE = "#334155", "#64748b", "#94a3b8", "#e2e8f0"
FONT = ('-apple-system, BlinkMacSystemFont, "PingFang SC", "Hiragino Sans GB", "Noto Sans CJK SC", '
        '"Microsoft YaHei", "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif')


def t(zh, en):
    return zh if LANG == "zh" else en


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


SIZES = {"t": 56, "k": 44, "m": 34, "b": 30, "s": 26, "f": 22}


def tw(s, size):
    """Approximate rendered width: CJK and full-width glyphs are 1em, the rest about 0.58em."""
    return sum(size if ord(c) > 0x2E80 else size * 0.58 for c in s)


TITLE = t("agent 需要一个池子", "Why Ollupi")


class Fig:
    def __init__(self, n, title, source=""):
        foot = t(f"图 {n}", f"Fig. {n}") + (f" · {source}" if source else "")
        self.p = [
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}">',
            "<defs>" + "".join(
                f'<marker id="{mid}" viewBox="0 0 10 10" refX="8" refY="5" markerUnits="userSpaceOnUse" '
                f'markerWidth="24" markerHeight="24" orient="auto-start-reverse"><path d="M0,1 L9,5 L0,9 z" '
                f'fill="{c}"/></marker>'
                for mid, c in (("aS", SLATE), ("aI", INDIGO), ("aR", ROSE), ("aF", SLATE_2))) + "</defs>",
            f"<style>text {{ font-family: {FONT}; fill: {INDIGO_DEEP}; }}"
            f" .t {{ font-size: 56px; font-weight: 800; }}"
            f" .k {{ font-size: 44px; font-weight: 800; }}"
            f" .m {{ font-size: 34px; font-weight: 700; }}"
            f" .b {{ font-size: 30px; fill: {INK2}; }}"
            f" .s {{ font-size: 26px; fill: {MUTED}; }}"
            f" .f {{ font-size: 22px; fill: {FAINT}; }}</style>",
            f'<rect width="{W}" height="{H}" fill="#ffffff"/>',
            f'<text class="t" x="{PAD}" y="118" style="font-size:{min(56, (W - 2 * PAD) / tw(title, 1)):.1f}px">'
            f'{esc(title)}</text>',
            f'<line x1="{PAD}" y1="{H - 72}" x2="{W - PAD}" y2="{H - 72}" stroke="{RULE}" stroke-width="2"/>',
            f'<text class="f" x="{PAD}" y="{H - 34}">{esc(foot)}</text>',
            f'<text class="f" x="{W - PAD}" y="{H - 34}" text-anchor="end">{esc(TITLE)}</text>',
        ]

    def add(self, s):
        self.p.append(s)

    def text(self, x, y, s, cls, anchor="start", fill=None, maxw=None, weight=None):
        styles = [f"fill:{fill}"] if fill else []
        if weight:
            styles.append(f"font-weight:{weight}")
        if maxw and tw(s, SIZES[cls]) > maxw:
            styles.append(f"font-size:{SIZES[cls] * maxw / tw(s, SIZES[cls]):.1f}px")
        st = f' style="{";".join(styles)}"' if styles else ""
        self.add(f'<text class="{cls}" x="{x:.1f}" y="{y:.1f}" text-anchor="{anchor}"{st}>{esc(s)}</text>')

    def lines(self, x, y, lines, cls, lh=None, anchor="start", fill=None, maxw=None, weight=None):
        """Draw a list of lines, first baseline at y. Returns the y below the last line."""
        lh = lh or SIZES[cls] * 1.35
        for i, ln in enumerate(lines):
            self.text(x, y + i * lh, ln, cls, anchor, fill, maxw, weight)
        return y + len(lines) * lh

    def rect(self, x, y, w, h, fill, stroke="none", r=16, sw=3, dash=False):
        d = ' stroke-dasharray="12 9"' if dash else ""
        self.add(f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="{r}" fill="{fill}" '
                 f'stroke="{stroke}" stroke-width="{sw}"{d}/>')

    def chip(self, x, y, w, h, lines, fill, stroke="none", cls="s", color=None, r=14, dash=False, weight=None):
        """A box with its lines centred in it."""
        self.rect(x, y, w, h, fill, stroke, r=r, sw=3, dash=dash)
        size = SIZES[cls]
        lh = size * 1.3
        y0 = y + h / 2 - (len(lines) - 1) * lh / 2 + size * 0.36
        for i, ln in enumerate(lines):
            self.text(x + w / 2, y0 + i * lh, ln, cls, "middle", color, maxw=w - 20, weight=weight)

    def arrow(self, x1, y1, x2, y2, mid="aS", color=SLATE, sw=4, dash=False):
        st = ' stroke-dasharray="12 9"' if dash else ""
        self.add(f'<path d="M{x1:.1f},{y1:.1f} L{x2:.1f},{y2:.1f}" fill="none" stroke="{color}" stroke-width="{sw}" '
                 f'stroke-linecap="round" marker-end="url(#{mid})"{st}/>')

    def mark(self, cx, cy, ok, r=24):
        """A ✓ (teal) / ✕ (rose) disc."""
        self.add(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r}" fill="{TEAL if ok else ROSE}"/>')
        k = r / 12
        if ok:
            self.add(f'<path d="M{cx - 5 * k:.1f},{cy:.1f} L{cx - 1.5 * k:.1f},{cy + 4 * k:.1f} '
                     f'L{cx + 5.5 * k:.1f},{cy - 4 * k:.1f}" fill="none" stroke="#fff" stroke-width="{2.6 * k:.1f}" '
                     f'stroke-linecap="round" stroke-linejoin="round"/>')
        else:
            self.add(f'<path d="M{cx - 4.5 * k:.1f},{cy - 4.5 * k:.1f} L{cx + 4.5 * k:.1f},{cy + 4.5 * k:.1f} '
                     f'M{cx + 4.5 * k:.1f},{cy - 4.5 * k:.1f} L{cx - 4.5 * k:.1f},{cy + 4.5 * k:.1f}" stroke="#fff" '
                     f'stroke-width="{2.6 * k:.1f}" stroke-linecap="round"/>')

    def badge(self, cx, cy, n, r=22):
        """A numbered disc: the condition it marks, the same in every figure."""
        self.add(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r}" fill="{INDIGO}" stroke="#ffffff" stroke-width="4"/>')
        self.add(f'<text x="{cx:.1f}" y="{cy + r * 0.4:.1f}" text-anchor="middle" '
                 f'style="font-size:{r * 1.15:.0f}px;font-weight:800;fill:#ffffff">{n}</text>')

    def bolt(self, cx, cy, s=1.0):
        """A crash: a rose lightning bolt."""
        pts = [(-6, -26), (10, -26), (2, -4), (14, -4), (-8, 28), (-2, 4), (-14, 4)]
        d = "M" + " L".join(f"{cx + px * s:.1f},{cy + py * s:.1f}" for px, py in pts) + " Z"
        self.add(f'<path d="{d}" fill="{ROSE}"/>')

    def save(self, name):
        path = os.path.join(OUT, name + ".svg")
        with open(path, "w") as f:
            f.write("\n".join(self.p + ["</svg>"]) + "\n")
        return path


# Figure numbers follow the order the figures appear on the page.
NUM = {name: i + 1 for i, name in enumerate(["waiting", "pool", "lifecycle", "anatomy", "matrix", "burst", "tradeoff"])}


def fig_pool():
    """The same problem a third time: connections, servers, and now agents go into a pool."""
    f = Fig(NUM["pool"], t("连接和服务器已经池化，下一个是 agent", "Connections and servers went into pools; agents are next"))
    rows = [
        (t("HTTP / RPC 框架", "HTTP / RPC"), t("请求：数量不限", "Requests: no limit"), t("连接池：连接数有上限", "Connection pool: few connections"), False),
        (t("云服务", "Cloud providers"), t("用户申请的资源：看似不限", "What users reserve: seemingly unlimited"),
         t("物理机池：按实际用量分配，闲置转给他人", "Server pool: shared by actual use"), False),
        (t("agent 运行时", "Agent runtime"), t("会话：数量不限", "Sessions: no limit"), t("agent 池：槽位和配额有上限", "Agent pool: few slots, one quota"), True),
    ]
    rh, rg, y0 = 180, 24, 176
    dx, dcols, drows, dp = 400, 16, 4, 25
    px, pw = 980, W - PAD - 980
    for r, (label, demand, pool, ours) in enumerate(rows):
        y = y0 + r * (rh + rg)
        f.text(PAD, y + rh / 2 + 4, label, "m", fill=INDIGO if ours else INDIGO_DEEP, maxw=300)
        for i in range(dcols * drows):
            cx, cy = dx + 12 + (i % dcols) * dp, y + 30 + (i // dcols) * dp
            f.add(f'<circle cx="{cx}" cy="{cy}" r="7" fill="{SLATE_TINT}" stroke="{SLATE}" stroke-width="1.5"/>')
        f.text(dx, y + rh - 22, demand, "s")
        f.arrow(dx + dcols * dp + 20, y + 68, px - 24, y + 68, mid="aI" if ours else "aS", color=INDIGO if ours else SLATE)
        f.rect(px, y + 6, pw, rh - 12, TINT if ours else "#ffffff", INDIGO if ours else SLATE)
        n, cw, gap = 6, 64, 14
        x0 = px + (pw - (n * cw + (n - 1) * gap)) / 2
        for k in range(n):
            busy = k < 4
            f.rect(x0 + k * (cw + gap), y + 26, cw, cw, INDIGO if busy else "#ffffff", "none" if busy else SLATE_2, r=10)
        f.text(px + pw / 2, y + rh - 26, pool, "s", "middle", fill=INDIGO_DEEP, maxw=pw - 30)
    return f.save(f"why-fig-{NUM['pool']}-pool")


def fig_anatomy():
    """The whole picture: a session pool and a tool pool, sandboxes apart, state in the database, a record before each tool call."""
    f = Fig(NUM["anatomy"], t("池化 agent 的架构：四个条件各对应一处", "A pool of agents: four conditions, one place each"),
            t("示意", "Illustration"))
    # Queue: every session waits in one line.
    f.lines(PAD, 206, [t("所有会话", "Every session"), t("统一排队", "in one queue")], "b", lh=38, fill=INDIGO_DEEP, weight=700)
    qx, qy, qp = 112, 290, 40
    for i in range(24):
        cx, cy = qx + (i % 4) * qp, qy + (i // 4) * qp
        f.add(f'<circle cx="{cx}" cy="{cy}" r="12" fill="{SLATE_TINT}" stroke="{SLATE}" stroke-width="2"/>')
    # Two pools, each with its own scheduler: sessions get slots, asynchronous tool calls get coroutines.
    px, pw = 392, 600
    pools = [(190, t("会话池", "Session pool"), t("调度器分配槽位", "a scheduler hands out slots"), 6, 4),
             (362, t("工具池", "Tool pool"), t("调度器分配协程", "a scheduler runs the calls"), 6, 3)]
    ph = 128
    for y, name, sub, n, busy in pools:
        f.rect(px, y, pw, ph, TINT, INDIGO, r=20)
        f.text(px + 36, y + 56, name, "m")
        f.text(px + 36, y + 96, sub, "s", maxw=200)
        cw, gap = 44, 12
        x0 = px + pw - 30 - (n * cw + (n - 1) * gap)
        for k in range(n):
            on = k < busy
            if y == 190:
                f.rect(x0 + k * (cw + gap), y + 42, cw, cw, INDIGO if on else "#ffffff", "none" if on else SLATE_2, r=8)
            else:
                f.add(f'<circle cx="{x0 + k * (cw + gap) + cw / 2:.1f}" cy="{y + 64}" r="{cw / 2}" '
                      f'fill="{INDIGO if on else "#ffffff"}" stroke="{INDIGO if on else SLATE_2}" stroke-width="3"/>')
        f.badge(px, y, 1)
    f.arrow(qx + 4 * qp - 10, 254, px - 14, 254, mid="aI", color=INDIGO)
    # Between the pools: a session hands off a long tool call and later gets the report back.
    ax = px + 300
    f.arrow(ax - 20, 190 + ph + 6, ax - 20, 362 - 6, sw=3)
    f.arrow(ax + 20, 362 - 6, ax + 20, 190 + ph + 6, sw=3)
    f.text(ax - 34, 352, t("转入后台", "in the background"), "f", "end")
    f.text(ax + 34, 352, t("返回报告", "report back"), "f")
    py, ph = 190, 362 + ph - 190
    # The model provider.
    mx, mw = 1092, W - PAD - 1092
    f.chip(mx, 196, mw, 84, [t("模型调用：按配额限流", "Model calls: rate-limited by quota")], SLATE_TINT, "none", "s", INDIGO_DEEP)
    f.arrow(px + pw + 12, 238, mx - 12, 238)
    f.badge(mx, 196, 1)
    # Sandboxes: commands run outside the runtime, each in its session's own box.
    sy = 570
    centers = [px + 140 + k * 95 for k in range(4)]
    for cx in centers:
        f.add(f'<line x1="{cx}" y1="{py + ph}" x2="{cx}" y2="{sy}" stroke="{SLATE}" stroke-width="2.5" stroke-dasharray="6 6"/>')
        f.chip(cx - 40, sy, 80, 70, [t("沙箱", "Box")], "#ffffff", SLATE, "s", INK2, r=12, dash=True)
    f.badge(centers[0] - 44, sy, 2)
    f.lines(centers[-1] + 60, sy + 26, [t("命令在各自的", "Commands run"), t("沙箱中执行", "in their own box")], "s", lh=34)
    # The database: one log per session; a waiting session is only these rows.
    dx, dy, dw, dh = 1092, 340, W - PAD - 1092, 380
    f.rect(dx, dy, dw, dh, "#ffffff", SLATE, r=20)
    f.text(dx + 34, dy + 56, t("数据库：每个会话一份日志", "Database: a log per session"), "b", weight=700, maxw=dw - 68)
    f.text(dx + 34, dy + 94, t("等待中的会话只保留日志", "A waiting session is just these rows"), "s", maxw=dw - 68)
    rows = [t("用户消息", "User message"), t("模型回答", "Model answer"), t("开始：发邮件", "Started: send email"), t("结果", "Result")]
    for i, r_ in enumerate(rows):
        hot = i == 2
        f.chip(dx + 34, dy + 122 + i * 58, dw - 120, 46, [r_], TEAL_TINT if hot else TINT, TEAL if hot else "none", "s", INK2, r=10)
    f.badge(dx + dw - 44, dy + 122 + 2 * 58 + 23, 4, r=20)
    f.badge(dx, dy, 3)
    f.arrow(px + pw + 12, 430, dx - 12, 430, mid="aI", color=INDIGO)
    f.text((px + pw + dx) / 2, 410, t("逐步写入", "Writes"), "f", "middle")
    # Waking: back to the queue, any process can pick it up.
    wy = 784
    f.add(f'<path d="M{dx + dw / 2},{dy + dh + 6} L{dx + dw / 2},{wy} L{qx + 1.5 * qp},{wy} L{qx + 1.5 * qp},{qy + 5 * qp + 28}" '
          f'fill="none" stroke="{INDIGO}" stroke-width="4" stroke-linejoin="round" marker-end="url(#aI)"/>')
    f.text(700, wy - 16, t("轮到时唤醒，任一进程都能从断点继续", "When its turn comes, any process wakes it where it stopped"),
           "s", "middle", fill=INDIGO_DEEP)
    return f.save(f"why-fig-{NUM['anatomy']}-anatomy")


def fig_matrix():
    """Each approach against the four conditions, asked as yes-or-no questions."""
    f = Fig(NUM["matrix"], t("各方案满足哪几个条件", "Which conditions each approach meets"),
            t("灰：未测、需自建或不适用。依据见正文", "Grey: not measured, build it yourself, or not applicable"))
    cols = [(t("统一调度，", "Shared"), t("有资源上限？", "scheduling,"), t("", "with limits?")),
            (t("运行时共享，", "Shared runtime,"), t("只隔离命令？", "only commands"), t("", "isolated?")),
            (t("状态在进程外，", "State outside"), t("重启可恢复？", "the process,"), t("", "resumable?")),
            (t("唤醒时不重复", "Wakes without"), t("执行命令？", "running a"), t("", "command twice?"))]
    Y, NO = (t("是", "Yes"), "good"), (t("否", "No"), "bad")
    UNT, DIY = (t("未测", "Not measured"), "none"), (t("需自建", "Build it yourself"), "none")
    NA = (t("不续跑", "Never resumes"), "none")
    rows = [
        (t("每个 agent 一台虚拟机", "A VM per agent"), [NO, NO, NO, NO]),
        (t("每个会话一个进程", "A process per session"), [NO, NO, UNT, UNT]),
        (t("一个进程承载多个会话", "Many sessions per process"), [NO, Y, NO, NA]),
        ("pi-durable", [NO, Y, Y, Y]),
        (t("持久化执行框架", "Durable execution"), [DIY, DIY, Y, NO]),
        ("Cloudflare", [DIY, DIY, Y, DIY]),
        ("Ollupi", [Y, Y, Y, Y]),
    ]
    lw = t(380, 440)
    cw = (W - 2 * PAD - lw) / 4
    for i, heads in enumerate(cols):
        x = PAD + lw + i * cw
        f.badge(x + 26, 176, i + 1, r=18)
        if LANG == "zh":
            f.text(x + 52, 186, heads[0], "s", fill=INDIGO_DEEP, weight=700, maxw=cw - 58)
            f.text(x + 52, 220, heads[1], "s", fill=INDIGO_DEEP, weight=700, maxw=cw - 58)
        else:
            f.lines(x + 52, 184, heads, "f", lh=28, fill=INDIGO_DEEP, weight=700)
    rh, y0 = 76, t(244, 256)
    style = {"bad": (ROSE_TINT, ROSE, INK2), "good": (TEAL_TINT, TEAL, INK2), "none": (SLATE_TINT, "none", MUTED)}
    for r, (name, cells) in enumerate(rows):
        y = y0 + r * rh
        ours = name == "Ollupi"
        f.text(PAD, y + rh / 2 + 10, name, "b", fill=INDIGO if ours else INDIGO_DEEP, maxw=lw - 24, weight=700 if ours else None)
        for i, (txt, kind) in enumerate(cells):
            fill, stroke, col = style[kind]
            x, w = PAD + lw + i * cw + 6, cw - 12
            if kind == "none":
                f.chip(x, y + 8, w, rh - 16, [txt], fill, stroke, "s", col, r=12)
            else:
                f.rect(x, y + 8, w, rh - 16, fill, stroke, r=12)
                f.mark(x + w / 2 - 26, y + rh / 2, kind == "good", r=16)
                f.text(x + w / 2 + 2, y + rh / 2 + 10, txt, "b", fill=col, weight=700)
    return f.save(f"why-fig-{NUM['matrix']}-matrix")


def fig_lifecycle():
    """One session as swimlanes. The session frame holds its model and tool calls; what it sends out runs outside it."""
    f = Fig(NUM["lifecycle"], t("会话的生命周期：哪些串行，哪些并发", "One session: what goes in turn, what runs at once"),
            t("示意，时间不按比例", "Illustration, time not to scale"))
    tx0, tx1 = 340, 1500

    def X(u):
        return tx0 + u / 100 * (tx1 - tx0)

    # Rows: (top, height). 0 = session header, 1 = model, 2 = tools (inside the frame); 3 = background tool, 4 = subagents.
    ft = 200
    rows = [(ft, 56), (ft + 56, 88), (ft + 144, 96), (ft + 286, 84), (ft + 370, 116)]
    fb = rows[2][0] + rows[2][1]
    bottom = rows[4][0] + rows[4][1]

    def mid(i):
        return rows[i][0] + rows[i][1] / 2

    def bar(i, u0, u1, fill, label="", h=48, dy=0, stroke="none", dash=False, color="#ffffff", sw=3):
        y = mid(i) - h / 2 + dy
        f.add(f'<rect x="{X(u0):.1f}" y="{y:.1f}" width="{X(u1) - X(u0) - 4:.1f}" height="{h}" rx="{min(10, h / 2)}" '
              f'fill="{fill}" stroke="{stroke}" stroke-width="{sw}"' + (' stroke-dasharray="12 9"' if dash else "") + "/>")
        if label:
            f.text((X(u0) + X(u1)) / 2, y + h / 2 + 9, label, "s", "middle", fill=color, maxw=X(u1) - X(u0) - 20)

    # The session frame: it holds the model calls and tool calls of its turns.
    for u0, u1 in ((0, 52), (88, 100)):
        f.rect(X(u0), ft + 8, X(u1) - X(u0) - 4, fb - ft - 16, TINT, "none", r=12)
        f.text(X(13) if u0 == 0 else (X(u0) + X(u1)) / 2, mid(0) + 9, t("运行中", "Running"), "s", "middle", fill=INDIGO_DEEP,
               weight=700)
    f.rect(X(52), ft + 8, X(88) - X(52) - 4, fb - ft - 16, "#ffffff", SLATE_2, r=12, dash=True)
    f.text((X(52) + X(88)) / 2, mid(0) + 9, t("等待下载的报告，不占槽位", "Waits, holding no slot"), "s", "middle",
           fill=MUTED)
    f.rect(PAD - 16, ft - 4, tx1 + 16 - (PAD - 16), fb - ft + 8, "none", INDIGO, r=18, sw=3)
    f.text(PAD, mid(0) + 11, t("会话", "Session"), "m", fill=INDIGO_DEEP)
    # The moment when several things run at once.
    b0, b1 = X(28), X(38)
    f.add(f'<rect x="{b0:.1f}" y="{ft - 12}" width="{b1 - b0:.1f}" height="{bottom - ft + 24}" rx="12" fill="{INDIGO}" '
          f'fill-opacity="0.06" stroke="{INDIGO}" stroke-width="2.5" stroke-dasharray="10 8"/>')
    f.text((b0 + b1) / 2, ft - 28, t("此刻并发：模型调用、下载、3 个子 agent", "At this moment: the model, a download, 3 subagents"),
           "s", "middle", fill=INDIGO_DEEP, weight=700)

    for i, name in ((1, t("模型调用", "Model calls")), (2, t("工具调用", "Tool calls")),
                    (3, t("后台工具", "Background tool")), (4, t("子 agent", "Subagents"))):
        f.text(PAD + 28 if i < 3 else PAD, mid(i) + 10, name, "b", weight=700, fill=INDIGO_DEEP)
    f.add(f'<line x1="{PAD + 28}" y1="{rows[2][0]}" x2="{tx1}" y2="{rows[2][0]}" stroke="{LINE}" stroke-width="2"/>')
    f.add(f'<line x1="{PAD}" y1="{rows[4][0]}" x2="{tx1}" y2="{rows[4][0]}" stroke="{RULE}" stroke-width="2"/>')
    f.text(PAD, fb + 40, t("由会话派生，在会话之外执行：", "Sent out by the session, run outside it:"), "s", weight=700)

    # Inside: model calls strictly one after another; three reads at once, then one command.
    for u0, u1 in ((1, 11), (15.5, 25.5), (28, 38), (42, 51.5), (89, 99)):
        bar(1, u0, u1, INDIGO, t("模型", "Model"))
    for k in (-1, 0, 1):
        bar(2, 11, 15.5, SLATE, h=24, dy=k * 30)
    f.lines(X(15.8), mid(2) - 6, [t("3 个读取", "3 reads"), t("并发执行", "at once")], "f", lh=28)
    bar(2, 38, 42, SLATE, h=48)
    f.text(X(42.3), mid(2) + 8, t("执行命令", "Command"), "f")

    # Sent out after the second model call.
    vx = X(25.5) - 2
    f.add(f'<path d="M{vx:.1f},{mid(1) + 26} L{vx:.1f},{mid(4) + 34}" fill="none" stroke="{SLATE}" stroke-width="3" '
          f'stroke-dasharray="8 7"/>')
    f.arrow(vx, mid(3), X(28.5) - 4, mid(3), "aS", SLATE, sw=3)
    for k in (-1, 0, 1):
        f.add(f'<path d="M{vx:.1f},{mid(4) + k * 34:.1f} L{X(28.5) - 6:.1f},{mid(4) + k * 34:.1f}" stroke="{SLATE}" '
              f'stroke-width="3"/>')
    f.text(vx - 12, mid(3) + 8, t("派生", "Sends out"), "f", "end")
    # Background tool: the download, reporting back into the session frame.
    bar(3, 28.5, 88, SLATE, t("下载文件：数十分钟", "Download: tens of minutes"))
    rx = X(88) - 2
    f.arrow(rx, mid(3) - 26, rx, ft + 10, "aS", SLATE, sw=3)
    f.text(rx - 14, mid(2) + 8, t("返回报告", "Reports back"), "f", "end")
    # Subagents: each a small session frame with its own model calls.
    for k, u1 in ((-1, 46), (0, 50), (1, 43)):
        y = mid(4) + k * 34 - 14
        f.rect(X(28.5), y, X(u1) - X(28.5), 28, TINT, INDIGO_2, r=8, sw=2)
        for j in range(3):
            u = 29.5 + j * (u1 - 31) / 3
            f.rect(X(u), y + 6, 26, 16, INDIGO, "none", r=4)
    f.text(X(51), mid(4) + 8, t("完成后各自返回报告", "Each reports back when done"), "f")
    # Time axis.
    ay = bottom + 30
    f.arrow(tx0, ay, tx1, ay, "aF", SLATE_2, sw=3)
    f.text(tx0 - 16, ay + 8, t("时间", "Time"), "f", "end")
    # Legend: what each colour waits on.
    ly, lx = ay + 56, PAD
    for col, label in ((INDIGO, t("模型调用：受限于服务商配额与本机并发上限", "Model calls: wait on the provider's quota and a local cap")),
                       (SLATE, t("工具执行：受限于本机 CPU、磁盘、网络与端口", "Tool runs: wait on local CPU, disk, network, ports"))):
        f.rect(lx, ly - 22, 44, 28, col, "none", r=6)
        f.text(lx + 58, ly, label, "s", fill=INK2)
        if LANG == "zh":
            lx += 58 + tw(label, 26) + 64
        else:
            ly += 40
    return f.save(f"why-fig-{NUM['lifecycle']}-lifecycle")


def fig_waiting():
    """Before any pool: hundreds of subagents start at once, and the user can only throttle by how slow the machine feels."""
    import random
    rnd = random.Random(11)
    f = Fig(NUM["waiting"], t("八百个任务同时运行，只能凭机器卡顿程度控制节奏", "800 tasks at once; the only control is how slow the machine feels"),
            t("示意，非实测", "Illustration, not a measurement"))
    # The fan-out: 800 subagents, one per surviving roll, all started at once.
    cols, rows, pitch = 40, 20, 15
    gx, gy = 560, 214
    n_big = cols * rows
    ids = list(range(n_big))
    rnd.shuffle(ids)
    model, refused = set(ids[:140]), set(ids[140:400])
    rx_, ry_ = PAD, 300
    f.chip(rx_, ry_ - 40, 330, 80, [t("用户的会话", "The user's session")], SLATE_TINT, SLATE_2, "b", INDIGO_DEEP)
    f.lines(rx_, ry_ + 84, [t("“整理《永乐大典》存本”", "\"Collect the surviving"), t("每卷派生一个子 agent", "Yongle Encyclopedia\""),
                            t("", "One subagent per roll")][:2 if LANG == "zh" else 3], "s", lh=34)
    for k in range(0, rows, 3):
        cy = gy + k * pitch
        f.add(f'<path d="M{rx_ + 330},{ry_} C{(rx_ + 330 + gx) / 2},{ry_} {(rx_ + 330 + gx) / 2},{cy} {gx - 10},{cy}" '
              f'fill="none" stroke="{SLATE_2}" stroke-width="1.5"/>')

    def dot(cx, cy, state, r):
        fill, stroke = {"m": (INDIGO, INDIGO), "r": (ROSE, ROSE), "w": (SLATE_TINT, SLATE)}[state]
        f.add(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{fill}" stroke="{stroke}" stroke-width="1.2"/>')

    for i in range(n_big):
        dot(gx + (i % cols) * pitch, gy + (i // cols) * pitch, "m" if i in model else "r" if i in refused else "w", 4.5)
    ly = gy + rows * pitch + 30
    lx = gx
    for k, (state, label) in enumerate((("m", t("调用模型", "Calling the model")), ("r", t("被拒、重试", "Refused, retrying")),
                                        ("w", t("等待工具返回", "Waiting on a tool")))):
        if LANG != "zh" and k == 2:
            lx, ly = gx, ly + 40
        dot(lx + 8, ly - 8, state, 8)
        f.text(lx + 26, ly, label, "s")
        lx += 26 + tw(label, 26) + 40
    # Other work on the same machine.
    small = [(t("定时任务", "Scheduled task"), "mwr"), (t("聊天软件的消息", "Message from a chat app"), "rmwrw"),
             (t("其他会话", "Other sessions"), "wr")]
    for j, (label, states) in enumerate(small):
        y = 666 + j * 58
        f.chip(PAD, y - 24, 330, 48, [label], SLATE_TINT, SLATE_2, "s", INDIGO_DEEP, r=12)
        f.add(f'<line x1="{PAD + 330}" y1="{y}" x2="{gx - 10}" y2="{y}" stroke="{SLATE_2}" stroke-width="1.5"/>')
        for k, st in enumerate(states):
            dot(gx + k * 34, y, st, 9)
    # The machine.
    tx = 1220
    f.text(tx, 236, t("本机", "This machine"), "b", weight=700, fill=INDIGO_DEEP)
    for k, (label, frac, note) in enumerate(((t("模型配额", "Model quota"), 1.0, t("打满", "exhausted")),
                                             (t("内存", "Memory"), 0.92, t("吃紧", "tight")),
                                             (t("CPU", "CPU"), 0.86, t("吃紧", "tight")))):
        y = 296 + k * 84
        f.text(tx, y, label, "s", fill=INK2)
        f.text(W - PAD, y, note, "s", "end", fill=ROSE)
        f.rect(tx, y + 14, W - PAD - tx, 22, SLATE_TINT, "none", r=11)
        f.rect(tx, y + 14, (W - PAD - tx) * frac, 22, ROSE, "none", r=11)
    f.lines(tx, 568, [t("机器变卡，", "The machine lags;"), t("模型请求成批被拒", "calls fail in bulk")], "s", lh=36,
            maxw=W - PAD - tx)
    # The only control the user has: slow down new tasks.
    bx, by, bw, bh = 840, 650, W - PAD - 840, 136
    f.rect(bx, by, bw, bh, TINT, LINE, r=16)
    f.text(bx + 28, by + 54, t("用户能做的", "What the user can do"), "b", weight=700, fill=INDIGO_DEEP)
    f.text(bx + 28, by + 100, t("机器一卡，就放慢新建任务", "When it lags, start fewer tasks"), "s", maxw=380)
    sx0, sx1, sy = bx + bw - 250, bx + bw - 36, by + 56
    f.rect(sx0, sy - 6, sx1 - sx0, 12, "#ffffff", SLATE_2, r=6, sw=2)
    f.rect(sx0, sy - 6, 64, 12, INDIGO, "none", r=6)
    f.add(f'<circle cx="{sx0 + 64}" cy="{sy}" r="16" fill="#ffffff" stroke="{INDIGO}" stroke-width="4"/>')
    f.text(sx0, sy + 46, t("慢", "slow"), "f")
    f.text(sx1, sy + 46, t("快", "fast"), "f", "end")
    f.text((sx0 + sx1) / 2, sy + 46, t("新建速度", "new tasks"), "f", "middle")
    return f.save(f"why-fig-{NUM['waiting']}-waiting")


def fig_burst():
    """Many sessions in one process: bursts fail in bulk, and a kill loses the turn."""
    f = Fig(NUM["burst"], t("实测：缺条件 1 突发时成批失败，缺条件 3 被杀后中断", "Measured: without 1, bursts fail; without 3, kills stop turns"),
            t("基准：2026-11-19，Apple M1，模拟的模型和工具；Ollupi 测于 v0.18.0",
              "Benchmarks: 2026-11-19, Apple M1, simulated model and tools; Ollupi measured on v0.18.0"))
    rows = [(t("pi 的 SDK", "pi SDK"), 2517, False, t("中断，不再继续", "Stopped for good")),
            ("pi-durable", 2473, True, t("全部完成", "All complete")),
            ("DeepSeek Harness", 1236, False, t("标为中断，不再继续", "Ends interrupted")),
            ("Ollupi", 0, True, t("全部完成", "All complete"))]
    lx, rx = PAD, 900
    f.badge(lx + 20, 189, 1, r=20)
    f.text(lx + 52, 200, t("3000 个轮次同时提交，配额 256", "3000 turns at once, quota 256"), "m", maxw=rx - 110 - lx)
    f.text(lx + 52, 240, t("失败的轮次", "Turns that failed"), "s")
    f.badge(rx + 20, 189, 3, r=20)
    f.text(rx + 52, 200, t("进程被杀之后", "After kill -9"), "m")
    f.text(rx + 52, 240, t("进行中的轮次", "Turns in progress"), "s")
    bx, bmax = lx + 290, 400
    for i, (name, failed, ok, after) in enumerate(rows):
        y = 330 + i * 110
        ours = name == "Ollupi"
        col = INDIGO if ours else INDIGO_DEEP
        f.text(lx, y + 10, name, "b", fill=col, maxw=270, weight=700 if ours else None)
        w = bmax * failed / 3000
        if failed:
            f.rect(bx, y - 22, w, 44, ROSE_TINT, ROSE, r=8, sw=2)
        f.text(bx + w + 16, y + 12, f"{failed}", "m", fill=ROSE if failed else TEAL)
        f.text(rx, y + 10, name, "b", fill=col, maxw=270, weight=700 if ours else None)
        f.mark(rx + 300, y, ok, r=20)
        f.text(rx + 336, y + 10, after, "b", maxw=W - PAD - rx - 336)
    f.add(f'<line x1="{rx - 50}" y1="300" x2="{rx - 50}" y2="700" stroke="{RULE}" stroke-width="3"/>')
    f.text(lx, 770, t("三个 harness 均未统一限制模型调用并发，只能失败重试", "None of the three caps model calls; they only retry"), "s")
    return f.save(f"why-fig-{NUM['burst']}-burst")


def fig_tradeoff():
    """Ollupi against Cloudflare, item by item."""
    f = Fig(NUM["tradeoff"], t("Ollupi 胜在单机效率，Cloudflare 胜在扩展与可靠性", "Ollupi wins on one machine; Cloudflare wins at scale"),
            t("按原理比较，未实测", "Compared from how each works, not measured"))
    cx = W / 2
    top, bot = 190, 770
    f.add(f'<line x1="{cx}" y1="{top}" x2="{cx}" y2="{bot}" stroke="{RULE}" stroke-width="4"/>')
    f.text(cx - 40, top + 10, t("Ollupi 占优", "Ollupi ahead"), "m", "end", fill=INDIGO)
    f.text(cx + 40, top + 10, t("Cloudflare 占优", "Cloudflare ahead"), "m", fill=INDIGO_DEEP)
    left = [t("每步写库的延迟", "Latency of each write"), t("等模型时的成本", "Cost while waiting on the model")]
    right = [t("长会话每步的读取", "Reads per step in long chats"), t("单实例的会话容量", "How many sessions fit"),
             t("数据可靠性", "Durability of the data"), t("用户之间的隔离", "Isolation between users"),
             t("运维", "Operations")]
    pw, ph, step = 560, 72, 92
    for i, s in enumerate(left):
        f.chip(cx - 40 - pw, top + 50 + i * step, pw, ph, [s], TINT, INDIGO, "b", INDIGO_DEEP)
    for i, s in enumerate(right):
        f.chip(cx + 40, top + 50 + i * step, pw, ph, [s], SLATE_TINT, SLATE, "b", INDIGO_DEEP)
    my = top + 50 + 5 * step + 20
    mw = t(560, 920)
    f.chip(cx - mw / 2, my, mw, ph, [t("等待用户时的成本：相当，均只剩存储", "Cost while waiting on the user: even, storage only")], "#ffffff", SLATE_2,
           "b", INK2)
    return f.save(f"why-fig-{NUM['tradeoff']}-tradeoff")


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    for old in glob.glob(os.path.join(OUT, "why-fig-*.svg")):
        os.remove(old)
    for fn in (fig_waiting, fig_pool, fig_lifecycle, fig_anatomy, fig_matrix, fig_burst, fig_tradeoff):
        print(fn())
