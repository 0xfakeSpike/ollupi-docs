"""Figures for 《水在青天云在瓶：agent 的身首错位现象》.

Same visual system as ollupi/docs/images/figures.py: 1600 wide on white, eyebrow + title that states the point +
one line of context, footer rule. Each layer has one fixed color in every figure:
access = teal, runtime = indigo, execution = pink, model = slate, state = light indigo.
Isolation boundaries are rose and dashed. Text never takes a series color.

Run: python3 scripts/figures/head-in-the-cloud.py zh && python3 scripts/figures/head-in-the-cloud.py en
Output: docs/public/figures/head-in-the-cloud/fig-*.{zh,en}.svg (committed; the page links them).
"""
import os
import sys

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "docs", "public", "figures", "head-in-the-cloud")
LANG = sys.argv[1] if len(sys.argv) > 1 else "zh"
W, PAD = 1600, 72

INDIGO, INDIGO_2, INDIGO_DEEP = "#4f46e5", "#818cf8", "#1e1b4b"
TINT, LINE = "#eef2ff", "#c7d2fe"
ROSE, ROSE_TINT, ROSE_LINE = "#f43f5e", "#fff1f2", "#fecdd3"
PINK, PINK_TINT = "#ec4899", "#fdf2f8"
TEAL, TEAL_TINT = "#0d9488", "#f0fdfa"
SLATE, SLATE_TINT = "#64748b", "#f1f5f9"
INK2, MUTED, FAINT = "#334155", "#64748b", "#94a3b8"
RULE, BASE, PAPER = "#e2e8f0", "#cbd5e1", "#f8fafc"
FONT = ('-apple-system, BlinkMacSystemFont, "PingFang SC", "Hiragino Sans GB", "Noto Sans CJK SC", '
        '"Microsoft YaHei", "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif')
FOOT = "水在青天云在瓶：agent 的身首错位现象"

KIND = {  # fill, tint
    "access": (TEAL, TEAL_TINT),
    "runtime": (INDIGO, TINT),
    "exec": (PINK, PINK_TINT),
    "model": (SLATE, SLATE_TINT),
    "state": (INDIGO_2, TINT),
    "key": (INK2, SLATE_TINT),
}


EN = {
    # eyebrows, titles, subtitles, footers
    "图 1 · 引子": "FIG. 1 · OPENING",
    "运行时在海外，执行环境在自己的书桌上": "The runtime is overseas, the execution environment is on the desk",
    "不能直接访问模型服务的用户，把运行时搬到海外服务器，再把自己的电脑接回去":
        "Users who can't reach the model move the runtime to an overseas server, then tunnel their own computer back to it",
    "结构上与形态 5「云端运行时 + 本地执行」相同，成因不同": "Same structure as topology 5 (cloud runtime + local exec), different cause",
    "图 2 · 组成": "FIG. 2 · THE PARTS",
    "agent 由五部分组成，部分之间有三条边界": "An agent has five parts and three boundaries",
    "接入层、运行时、执行环境是通常说的三层；模型服务和会话状态同样影响部署位置":
        "The usual three layers, plus the model service and session state, which also shape where things run",
    "三条边界各自带来的工程问题见第五节": "The engineering problems at each boundary are covered in section 5",
    "图 3 · 九种部署形态": "FIG. 3 · NINE TOPOLOGIES",
    "同样三层，九种摆法": "Same three layers, nine arrangements",
    "按各部分部署在哪里分类。模型服务在所有形态中都在远端，图中省略；虚线表示可选位置":
        "Classified by where each part runs. The model service is remote in all of them and omitted; dashed means optional",
    "同一个产品可能支持多种形态": "One product may support several topologies",
    "图 4 · 决定部署位置的因素": "FIG. 4 · FORCES",
    "每个因素只拉动一部分，各部分因此被分开": "Each force pulls on one part, so the parts come apart",
    "七个因素分别作用于某一层，或某两层之间的边界": "Seven forces, each acting on one layer or on the boundary between two",
    "各因素的具体分析见第三节": "Each force is discussed in section 3",
    "图 5 · 形态 2 与形态 3": "FIG. 5 · TOPOLOGY 2 VS. 3",
    "Cowork 把 agent 循环移出了虚拟机": "Cowork moved the agent loop out of the VM",
    "调整前，运行时、凭证和代码执行在同一个虚拟机里；调整后，虚拟机里只剩代码执行":
        "Before, runtime, credentials and code execution shared one VM. After, only code execution is left inside",
    "依据：Anthropic《How we contain Claude across products》（2026-05）":
        "Source: Anthropic, “How we contain Claude across products” (May 2026)",
    "图 6 · 中国大陆": "FIG. 6 · MAINLAND CHINA",
    "同一个软件，在国内常被部署成另一种形态": "The same software often ships in a different topology in China",
    "各因素的权重变了：网络可达性和合规的分量更重": "The weights changed: network reachability and compliance count for more",
    "详见第四节": "See section 4",
    "图 7 · 控制方向反转": "FIG. 7 · INVERTED CONTROL",
    "运行时在云端时，最终的权限检查要放在本地": "When the runtime is in the cloud, enforce permissions locally",
    "连接由本地发起，指令由云端下发；云端运行时一旦被注入，本地检查是最后一道防线":
        "The local side dials out and the cloud sends instructions. If the runtime is injected, the local check is the last defense",
    "适用于形态 5，也适用于引子中的海外服务器方案": "Applies to topology 5 and to the overseas-server setup in fig. 1",
    "图 8 · 选型": "FIG. 8 · CHOOSING",
    "四个问题，选出部署形态": "Four questions pick the topology",
    "从上往下回答；「是」向右，「否」向下": "Answer from the top: yes goes right, no goes down",
    "企业场景把接入层换成企业 IM 即为形态 7；通用桌面助手可同时连接多个执行环境（形态 8）":
        "Enterprise: use the company chat app as the access layer (7). Desktop assistants: add execution envs (8)",
    # layers and chips
    "接入层": "Access layer", "运行时": "Runtime", "执行环境": "Execution environment", "模型服务": "Model service",
    "会话状态": "Session state", "接入": "Access", "执行": "Exec", "模型": "Model", "或在此执行": "or exec here",
    "迁移": "migrate",
    # fig 1
    "中国大陆 · 用户自己的电脑": "Mainland China · the user's computer",
    "终端、IDE": "Terminal, IDE", "代码、文件": "Code, files", "浏览器、开发环境": "Browser, dev tools",
    "资源都在这里": "All the resources are here", "地区边界": "Regional border",
    "海外 · 云服务器": "Overseas · cloud server", "Claude Code 等 agent": "Claude Code or similar",
    "模型账号凭证": "Model API key", "通往用户电脑的隧道": "Tunnel to the PC",
    "服务器被入侵 = 用户电脑被控制": "Server compromised = PC compromised",
    "海外 · 模型服务商": "Overseas · model provider", "Anthropic API": "Anthropic API",
    "内网穿透 / 反向隧道": "Reverse tunnel", "可访问": "Reachable", "无法直接访问": "Not reachable directly",
    # fig 2
    "桌面应用、网页、手机 app": "Desktop, web, mobile app", "终端、聊天软件机器人": "Terminal, chat-app bots",
    "组装上下文、调用模型": "Builds context, calls the model", "权限与审批、调度、重试": "Approvals, scheduling, retries",
    "shell、文件系统、浏览器": "Shell, file system, browser", "桌面应用、数据库、内网服务": "Desktop apps, databases, intranet",
    "对话记录、待执行任务、审批、记忆": "History, queue, approvals, memory",
    "① 会话协议": "① Session protocol", "② 工具调用": "② Tool calls", "③ 模型接口": "③ Model API",
    "持久化": "Persisted",
    # fig 3
    "用户设备": "User's device", "本地隔离区": "Local isolation", "用户的常开设备": "Always-on device", "云端": "Cloud",
    "全本地": "Fully local", "Claude Code、Codex CLI、Gemini CLI": "Claude Code, Codex CLI, Gemini CLI",
    "整体隔离": "Whole agent in a box", "devcontainer 中放开权限运行；早期的 Cowork": "Agent in a devcontainer; early Cowork",
    "本地运行时 + 隔离执行": "Local runtime + sandbox", "现在的 Cowork；Claude Code 沙箱模式": "Cowork today; Claude Code sandbox",
    "云端托管": "Cloud-hosted", "Devin、Manus、Codex cloud 等": "Devin, Manus, Codex cloud, etc.",
    "云端运行时 + 本地执行": "Cloud runtime + local exec", "Manus Browser Operator；引子中的方案": "Manus Browser Operator; fig. 1",
    "远程接入 + 本地运行时": "Remote access + home runtime",
    "Mac mini 上的 OpenClaw；Remote Control": "OpenClaw on a Mac mini; Remote Control",
    "聊天软件接入 + 云端": "Chat-app access + cloud", "飞书、钉钉、企业微信中的 agent；扣子": "Agents in Feishu, DingTalk, WeCom; Coze",
    "多执行环境": "Multiple execution envs", "Cowork；Manus 同时用云端与本地浏览器": "Cowork; Manus (cloud + local browser)",
    "会话迁移": "Session migration", "编码 agent 在本地与云端之间交接任务": "Tasks handed between local and cloud",
    # fig 4
    "网络可达性": "Network reachability", "运行时要能访问模型服务": "The runtime must reach the model",
    "安全隔离 · 故障隔离": "Security isolation · fault isolation",
    "凭证和审批权不与执行环境放在一起": "Keys and approvals stay away from execution",
    "执行环境出错不连累运行时": "Execution failures don't take the runtime down",
    "接入与身份": "Access and identity", "拉向用户已经在用的地方": "Toward where users already are",
    "在线时长": "Uptime", "拉向常开的地方": "Toward always-on machines",
    "资源位置": "Resource location", "拉向资源所在的地方": "Toward the resources",
    "闲置成本": "Idle cost",
    "三部分的生命周期不同：运行时共享、执行环境按需创建、接入层随时断开":
        "The parts live on different clocks: shared runtime, on-demand execution, clients that come and go",
    "合规": "Compliance",
    "反方向的力：数据不能离开某个范围，就把包括模型在内的所有部分圈在里面":
        "Pulls the other way: if data can't leave a boundary, every part, the model included, goes inside it",
    # fig 5
    "调整前：整体隔离（形态 2）": "Before: whole agent in a box (topology 2)",
    "调整后：本地运行时 + 隔离执行（形态 3）": "After: local runtime + sandbox (topology 3)",
    "宿主机": "Host", "虚拟机": "VM", "Cowork 界面": "Cowork UI", "agent 循环": "Agent loop", "凭证": "Credentials",
    "MCP 服务器": "MCP servers", "代码执行": "Code execution", "凭证（钥匙串）": "Credentials (keychain)",
    "代理：只放行本会话令牌": "Proxy: own token only", "会话令牌": "Token",
    "虚拟机启动失败，整个产品就不能用": "If the VM fails to boot, the whole product is down",
    "被注入的指令与凭证处在同一环境中": "Injected instructions share an environment with the keys",
    "虚拟机出错，只是一次工具调用失败": "A VM failure is just one failed tool call",
    "凭证留在宿主机，虚拟机只拿收窄、可吊销的令牌": "Keys stay on the host; the VM gets a scoped, revocable token",
    # fig 6
    "设计初衷 / 海外常见": "As designed / common abroad", "国内常见": "Common in China",
    "本地优先的 agent 网关": "Local-first agent gateway", "手机 · 聊天软件": "Phone · chat app",
    "家里的 Mac mini": "Mac mini at home", "飞书 / 钉钉 / 微信": "Chinese chat apps", "云厂商轻量服务器": "Chinese cloud VPS",
    "变成形态 7；网关端口从家庭网络暴露到公网": "Becomes topology 7; the gateway is now exposed to the internet",
    "本地编码 agent": "Local coding agent", "用户电脑": "User's PC",
    "a · 保留运行时，替换模型": "a · Keep the runtime, swap the model", "国产模型": "Chinese model",
    "b · 运行时在海外服务器（引子）": "b · Runtime on an overseas server (fig. 1)", "海外服务器": "Overseas server",
    # fig 7
    "用户的电脑": "User's computer", "浏览器、文件": "Browser, files", "登录状态": "Logged-in sessions",
    "权限检查": "Permission check", "最终在本地执行": "Enforced locally",
    "接收任务、调用模型": "Takes tasks, calls the model", "发出工具调用": "Issues tool calls",
    "可能被提示注入": "May be prompt-injected", "① 本地发起出站连接": "① Local dials out",
    "② 下发指令": "② Instructions", "③ 放行": "③ Allow",
    "不需要开放入站端口，设备没有公网地址也能连通": "No inbound port; works without a public IP",
    # fig 8
    "数据必须留在企业内网？": "Must data stay inside the company network?",
    "资源能复制到云端，且任务要并行或离线继续？": "Copyable resources, and need parallel or offline runs?",
    "任务比设备在线时间长，或要从手机派任务？": "Tasks outlive the device, or dispatched from a phone?",
    "希望 agent 自动运行，不逐条审批？": "Should the agent run without per-step approval?",
    "常开的运行时由谁提供？": "Who runs the always-on runtime?",
    "私有化部署": "On-premises deployment",
    "接入层、运行时、执行环境和模型都在内网": "Access, runtime, execution and model all inside the network",
    "4  云端托管": "4  Cloud-hosted", "换来并行和离线继续；付出本地资源和控制权": "Gains parallel and offline runs; costs local resources and control",
    "6  远程接入 + 本地运行时": "6  Home runtime", "5  云端运行时 + 本地执行": "5  Cloud runtime",
    "自己维护一台常开设备": "You maintain an always-on box", "权限检查放在本地": "Enforce permissions locally",
    "用户自己": "The user", "厂商": "A vendor",
    "3  本地运行时 + 隔离执行": "3  Local runtime + sandbox",
    "凭证留在隔离区外；执行环境出错不影响运行时": "Keys outside the sandbox; exec failures spare the runtime",
    "1  全本地": "1  Fully local", "零部署、零额外延迟；设备离线任务就停": "No setup, no added latency; stops when the device sleeps",
    "是": "Yes", "否": "No",
}


def t(zh, en=None):
    if LANG != "en":
        return zh
    return en or EN[zh]


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def tw(s, size):
    """Approximate rendered width: CJK and full-width glyphs are 1em, the rest about 0.58em."""
    return sum(size if ord(c) > 0x2E80 else size * 0.58 for c in s)


class Figure:
    def __init__(self, h, eyebrow, title, sub, foot_left):
        self.h = h
        markers = "".join(
            f'<marker id="{mid}" viewBox="0 0 10 10" refX="9" refY="5" markerUnits="userSpaceOnUse" markerWidth="12" '
            f'markerHeight="12" orient="auto-start-reverse"><path d="M0,1 L9,5 L0,9 z" fill="{c}"/></marker>'
            for mid, c in (("arrow", FAINT), ("arrowI", INDIGO), ("arrowR", ROSE)))
        self.p = [
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {h}" width="{W}" height="{h}">',
            f"<defs>{markers}</defs>",
            f"<style>text {{ font-family: {FONT}; fill: {INDIGO_DEEP}; }}"
            f" .eyebrow {{ font-size: 16px; font-weight: 600; letter-spacing: 3px; fill: {INDIGO}; }}"
            f" .title {{ font-size: 36px; font-weight: 700; }}"
            f" .sub {{ font-size: 19px; fill: {MUTED}; }}"
            f" .h {{ font-size: 22px; font-weight: 700; }}"
            f" .hs {{ font-size: 19px; font-weight: 600; }}"
            f" .q {{ font-size: 18px; font-weight: 700; }}"
            f" .b {{ font-size: 17px; fill: {INK2}; }}"
            f" .s {{ font-size: 15px; fill: {MUTED}; }}"
            f" .zt {{ font-size: 16px; font-weight: 600; fill: {MUTED}; letter-spacing: 1px; }}"
            f" .lab {{ font-size: 16px; fill: {INK2}; }}"
            f" .chip {{ font-size: 15px; font-weight: 600; }}"
            f" .chipb {{ font-size: 18px; font-weight: 700; }}"
            f" .foot {{ font-size: 15px; fill: {FAINT}; }}</style>",
            f'<rect width="{W}" height="{h}" fill="#ffffff"/>',
            f'<text class="eyebrow" x="{PAD}" y="62">{esc(eyebrow)}</text>',
            f'<text class="title" x="{PAD}" y="106">{esc(title)}</text>',
            f'<text class="sub" x="{PAD}" y="146">{esc(sub)}</text>',
            f'<line x1="{PAD}" y1="{h - 60}" x2="{W - PAD}" y2="{h - 60}" stroke="{RULE}" stroke-width="2"/>',
            f'<text class="foot" x="{PAD}" y="{h - 28}">{esc(foot_left)}</text>',
            f'<text class="foot" x="{W - PAD}" y="{h - 28}" text-anchor="end">{esc(t(FOOT, "Head in the Cloud, Hands at Home"))}</text>',
        ]

    def add(self, s):
        self.p.append(s)

    def text(self, x, y, s, cls, anchor="start", style=""):
        st = f' style="{style}"' if style else ""
        self.p.append(f'<text class="{cls}" x="{x:.1f}" y="{y:.1f}" text-anchor="{anchor}"{st}>{esc(s)}</text>')

    def rect(self, x, y, w, h, fill, stroke="none", r=10, sw=2, dash=False):
        d = ' stroke-dasharray="8 6"' if dash else ""
        self.p.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="{r}" fill="{fill}" '
                      f'stroke="{stroke}" stroke-width="{sw}"{d}/>')

    def line(self, x1, y1, x2, y2, color=FAINT, sw=2, dash=False):
        d = ' stroke-dasharray="8 6"' if dash else ""
        self.p.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="{sw}"{d}/>')

    def arrow(self, d, color="faint", dash=False, both=False, sw=2):
        mid, c = {"faint": ("arrow", FAINT), "indigo": ("arrowI", INDIGO), "rose": ("arrowR", ROSE)}[color]
        st = ' stroke-dasharray="7 6"' if dash else ""
        start = f' marker-start="url(#{mid})"' if both else ""
        self.p.append(f'<path d="{d}" fill="none" stroke="{c}" stroke-width="{sw}" marker-end="url(#{mid})"{start}{st}/>')

    def label(self, x, y, s, cls="lab", bg=True, anchor="middle"):
        """Text on a white pad, for labels that sit on top of lines."""
        size = {"lab": 16, "s": 15, "b": 17, "q": 18}[cls]
        w = tw(s, size) + 16
        x0 = x - w / 2 if anchor == "middle" else (x if anchor == "start" else x - w)
        if bg:
            self.rect(x0, y - size - 4, w, size + 14, "#ffffff", r=6)
        self.text(x0 + w / 2, y, s, cls, "middle")

    # ---- building blocks ----

    def zone(self, x, y, w, h, kind, title):
        """A place: device (white), cloud (paper), isolation (rose, dashed)."""
        if kind == "device":
            self.rect(x, y, w, h, "#ffffff", BASE, r=16)
        elif kind == "cloud":
            self.rect(x, y, w, h, PAPER, BASE, r=16)
        else:
            self.rect(x, y, w, h, ROSE_TINT, ROSE, r=16, dash=True)
        if title:
            self.text(x + 20, y + 30, title, "zt")

    def chip(self, x, y, kind, label, h=34, dash=False, w=None, cls="chip"):
        fill, tint = KIND[kind]
        size = 18 if cls == "chipb" else 15
        w = w or tw(label, size) + 28
        if dash:
            self.rect(x, y, w, h, tint, fill, r=8, dash=True)
            self.text(x + w / 2, y + h / 2 + size * 0.36, label, cls, "middle", f"fill:{fill}")
        else:
            self.rect(x, y, w, h, fill, r=8)
            self.text(x + w / 2, y + h / 2 + size * 0.36, label, cls, "middle", "fill:#ffffff")
        return w

    def chips(self, x, y, w, items, h=34, gap=8):
        """Lay chips out centered in a box of width w, wrapping to a second row if needed. items: (kind, label, dash)."""
        widths = [tw(lbl, 15) + 28 for _, lbl, _ in items]
        rows, cur, cw = [], [], 0
        for it, wd in zip(items, widths):
            if cur and cw + gap + wd > w:
                rows.append((cur, cw))
                cur, cw = [], 0
            cw += (gap if cur else 0) + wd
            cur.append((it, wd))
        rows.append((cur, cw))
        boxes = []
        for r, (row, rw) in enumerate(rows):
            cx = x + (w - rw) / 2
            for (kind, lbl, dash), wd in row:
                self.chip(cx, y + r * (h + gap), kind, lbl, h, dash)
                boxes.append((cx, y + r * (h + gap), wd))
                cx += wd + gap
        return boxes

    def layer(self, x, y, w, kind, name, lines=()):
        """A layer card: colored header with the layer's name, detail lines below."""
        fill, tint = KIND[kind]
        h = 48 + (len(lines) * 26 + 14 if lines else 0)
        self.rect(x, y, w, h, tint if lines else fill, fill if lines else "none", r=12)
        self.rect(x, y, w, 48, fill, r=12)
        if lines:
            self.rect(x, y + 36, w, 12, fill, r=0)
        self.text(x + w / 2, y + 31, name, "hs", "middle", "fill:#ffffff")
        for i, ln in enumerate(lines):
            self.text(x + w / 2, y + 48 + 26 + i * 26, ln, "lab", "middle")
        return h

    def card(self, x, y, w, title, lines=(), stroke=LINE, fill="#ffffff", cls="q"):
        h = 30 + 18 + len(lines) * 24 + 4
        self.rect(x, y, w, h, fill, stroke, r=12)
        self.text(x + 20, y + 34, title, cls)
        for i, ln in enumerate(lines):
            self.text(x + 20, y + 34 + 26 + i * 24, ln, "lab")
        return h

    def mark(self, x, y, ok):
        """A small ✓ / ✕ disc."""
        c = INDIGO if ok else ROSE
        self.add(f'<circle cx="{x}" cy="{y}" r="11" fill="{c}"/>')
        if ok:
            self.add(f'<path d="M{x-5},{y} L{x-1.5},{y+4} L{x+5.5},{y-4}" fill="none" stroke="#fff" stroke-width="2.6" '
                     f'stroke-linecap="round" stroke-linejoin="round"/>')
        else:
            self.add(f'<path d="M{x-4.5},{y-4.5} L{x+4.5},{y+4.5} M{x+4.5},{y-4.5} L{x-4.5},{y+4.5}" stroke="#fff" '
                     f'stroke-width="2.6" stroke-linecap="round"/>')

    def legend(self, x, y, kinds):
        """Chips right-aligned to x."""
        names = {"access": t("接入层"), "runtime": t("运行时"), "exec": t("执行环境"), "model": t("模型服务"),
                 "state": t("会话状态")}
        cx = x
        for k in reversed(kinds):
            w = tw(names[k], 15) + 28
            cx -= w
            self.chip(cx, y, k, names[k], h=30)
            cx -= 10

    def save(self, name):
        path = f"{OUT}/{name}.{LANG}.svg"
        with open(path, "w") as f:
            f.write("\n".join(self.p + ["</svg>"]) + "\n")
        return path


# ---------------------------------------------------------------------------

def fig_intro():
    f = Figure(650, t("图 1 · 引子"), t("运行时在海外，执行环境在自己的书桌上"),
               t("不能直接访问模型服务的用户，把运行时搬到海外服务器，再把自己的电脑接回去"),
               t("结构上与形态 5「云端运行时 + 本地执行」相同，成因不同"))
    top, zh = 200, 270
    # user's computer
    f.zone(72, top, 520, zh, "device", t("中国大陆 · 用户自己的电脑"))
    f.layer(104, top + 56, 210, "access", t("接入层"), [t("终端、IDE")])
    f.layer(332, top + 56, 248, "exec", t("执行环境"), [t("代码、文件"), t("浏览器、开发环境")])
    f.text(332, top + zh - 26, t("资源都在这里"), "s", "middle")
    # border
    f.line(676, top - 10, 676, top + zh + 70, ROSE, 2, dash=True)
    f.label(676, top - 18, t("地区边界"), "s")
    # overseas server
    f.zone(760, top, 400, zh, "cloud", t("海外 · 云服务器"))
    f.layer(792, top + 56, 336, "runtime", t("运行时"), [t("Claude Code 等 agent")])
    f.chip(792, top + 160, "key", t("模型账号凭证"))
    f.chip(792 + tw(t("模型账号凭证"), 15) + 40, top + 160, "key", t("通往用户电脑的隧道"))
    f.text(960, top + zh - 30, t("服务器被入侵 = 用户电脑被控制"), "s", "middle")
    # model
    f.zone(1250, top, 278, zh, "cloud", t("海外 · 模型服务商"))
    f.layer(1280, top + 56, 218, "model", t("模型服务"), [t("Anthropic API")])
    # links
    y = top + 110
    f.arrow(f"M594,{y} H758", dash=True, both=True)
    f.label(676, y - 14, t("内网穿透 / 反向隧道"))
    f.arrow(f"M1162,{y} H1248")
    f.label(1205, y - 14, t("可访问"), "s")
    yb = top + zh + 42
    f.arrow(f"M332,{top + zh} V{yb} H1389 V{top + zh + 2}", color="rose", dash=True)
    f.mark(1000, yb, False)
    f.label(1000, yb + 36, t("无法直接访问"), "s", bg=False)
    return f.save("fig-1-intro")


def fig_parts():
    f = Figure(760, t("图 2 · 组成"), t("agent 由五部分组成，部分之间有三条边界"),
               t("接入层、运行时、执行环境是通常说的三层；模型服务和会话状态同样影响部署位置"),
               t("三条边界各自带来的工程问题见第五节"))
    f.legend(W - PAD, 170, ["access", "runtime", "exec", "model", "state"])
    ry = 360
    f.layer(96, ry, 340, "access", t("接入层"), [t("桌面应用、网页、手机 app"), t("终端、聊天软件机器人")])
    f.layer(630, ry, 340, "runtime", t("运行时"), [t("组装上下文、调用模型"), t("权限与审批、调度、重试")])
    f.layer(1164, ry, 340, "exec", t("执行环境"), [t("shell、文件系统、浏览器"), t("桌面应用、数据库、内网服务")])
    f.layer(620, 222, 360, "model", t("模型服务"))
    f.layer(620, 572, 360, "state", t("会话状态"), [t("对话记录、待执行任务、审批、记忆")])
    yy = ry + 60
    f.arrow(f"M438,{yy} H628", both=True)
    f.label(533, yy - 16, t("① 会话协议"))
    f.arrow(f"M972,{yy} H1162")
    f.label(1067, yy - 16, t("② 工具调用"))
    f.arrow(f"M800,{ry - 2} V272", both=True)
    f.label(870, 322, t("③ 模型接口"), anchor="start")
    f.arrow(f"M800,{ry + 114} V570", both=True)
    f.label(850, 528, t("持久化"), "s", anchor="start")
    return f.save("fig-2-parts")


FORMS = [
    # name, example, cells: device, isolation, always-on, cloud; each a list of (kind, label, dashed)
    (t("全本地"), t("Claude Code、Codex CLI、Gemini CLI"),
     [[("access", "接入", 0), ("runtime", "运行时", 0), ("exec", "执行", 0)], [], [], []]),
    (t("整体隔离"), t("devcontainer 中放开权限运行；早期的 Cowork"),
     [[("access", "接入", 0)], [("runtime", "运行时", 0), ("exec", "执行", 0)], [], []]),
    (t("本地运行时 + 隔离执行"), t("现在的 Cowork；Claude Code 沙箱模式"),
     [[("access", "接入", 0), ("runtime", "运行时", 0)], [("exec", "执行", 0)], [], [("exec", "或在此执行", 1)]]),
    (t("云端托管"), t("Devin、Manus、Codex cloud 等"),
     [[("access", "接入", 0)], [], [], [("runtime", "运行时", 0), ("exec", "执行", 0)]]),
    (t("云端运行时 + 本地执行"), t("Manus Browser Operator；引子中的方案"),
     [[("access", "接入", 0), ("exec", "执行", 0)], [], [], [("runtime", "运行时", 0)]]),
    (t("远程接入 + 本地运行时"), t("Mac mini 上的 OpenClaw；Remote Control"),
     [[("access", "接入", 0)], [], [("runtime", "运行时", 0), ("exec", "执行", 0)], []]),
    (t("聊天软件接入 + 云端"), t("飞书、钉钉、企业微信中的 agent；扣子"),
     [[("access", "接入", 0)], [], [], [("runtime", "运行时", 0), ("exec", "执行", 0)]]),
    (t("多执行环境"), t("Cowork；Manus 同时用云端与本地浏览器"),
     [[("access", "接入", 0), ("runtime", "运行时", 0), ("exec", "执行", 0)], [("exec", "执行", 0)], [],
      [("exec", "执行", 0)]]),
    (t("会话迁移"), t("编码 agent 在本地与云端之间交接任务"),
     [[("access", "接入", 0), ("runtime", "运行时", 0)], [], [], [("runtime", "运行时", 1)]]),
]


def fig_forms():
    rows, rh, top = len(FORMS), 92, 250
    h = top + 56 + rows * rh + 100
    f = Figure(h, t("图 3 · 九种部署形态"), t("同样三层，九种摆法"),
               t("按各部分部署在哪里分类。模型服务在所有形态中都在远端，图中省略；虚线表示可选位置"),
               t("同一个产品可能支持多种形态"))
    f.legend(W - PAD, 176, ["access", "runtime", "exec"])
    lx, lw = PAD, 380
    cols = [(t("用户设备"), "#ffffff"), (t("本地隔离区"), ROSE_TINT), (t("用户的常开设备"), "#ffffff"), (t("云端"), PAPER)]
    cw = (W - PAD - (lx + lw)) / 4
    body_top, body_h = top + 56, rows * rh
    for i, (name, fill) in enumerate(cols):
        x = lx + lw + i * cw
        f.rect(x + 4, top, cw - 8, 56 + body_h + 8, fill, ROSE if i == 1 else BASE, r=14, dash=(i == 1))
        f.text(x + cw / 2, top + 34, name, "hs", "middle")
    for r, (name, ex, cells) in enumerate(FORMS):
        y = body_top + r * rh
        if r:
            f.line(lx, y, W - PAD, y, RULE, 1.5)
        f.text(lx, y + 38, f"{r + 1}", "h", "start", f"fill:{INDIGO}")
        f.text(lx + 32, y + 38, name, "hs")
        f.text(lx + 32, y + 66, ex, "s")
        boxes = []
        for i, items in enumerate(cells):
            if items:
                items = [(k, t(lbl), d) for k, lbl, d in items]
                boxes.append(f.chips(lx + lw + i * cw + 8, y + 29, cw - 16, items))
        if r == len(FORMS) - 1:  # migration: dashed double arrow between the two runtimes
            (x0, y0, w0) = boxes[0][-1]
            (x1, y1, _) = boxes[1][0]
            f.arrow(f"M{x0 + w0 + 10},{y0 + 17} H{x1 - 10}", dash=True, both=True)
            f.label((x0 + w0 + x1) / 2, y0 + 10, t("迁移"), "s")
    return f.save("fig-3-forms")


def fig_cowork():
    f = Figure(860, t("图 5 · 形态 2 与形态 3"), t("Cowork 把 agent 循环移出了虚拟机"),
               t("调整前，运行时、凭证和代码执行在同一个虚拟机里；调整后，虚拟机里只剩代码执行"),
               t("依据：Anthropic《How we contain Claude across products》（2026-05）"))
    pw, top, zh = 700, 236, 420
    for i, x in enumerate((PAD, W - PAD - pw)):
        before = i == 0
        f.text(x, 210, t("调整前：整体隔离（形态 2）") if before else t("调整后：本地运行时 + 隔离执行（形态 3）"), "h")
        f.zone(x, top, pw, zh, "device", t("宿主机"))
        vx, vy, vw, vh = (x + 330, top + 56, 340, zh - 86) if before else (x + 360, top + 56, 310, zh - 86)
        f.zone(vx, vy, vw, vh, "iso", t("虚拟机"))
        f.layer(x + 32, top + 70, 250 if before else 220, "access", t("接入层"), [t("Cowork 界面")])
        if before:
            f.layer(vx + 30, vy + 50, vw - 60, "runtime", t("运行时"), [t("agent 循环")])
            cw1 = f.chip(vx + 30, vy + 158, "key", t("凭证"))
            f.chip(vx + 30 + cw1 + 12, vy + 158, "key", t("MCP 服务器"))
            f.layer(vx + 30, vy + 210, vw - 60, "exec", t("执行环境"), [t("代码执行")])
            f.arrow(f"M{x + 284},{top + 110} H{vx + 28}")
            notes = [(False, t("虚拟机启动失败，整个产品就不能用")), (False, t("被注入的指令与凭证处在同一环境中"))]
        else:
            f.layer(x + 32, top + 200, 220, "runtime", t("运行时"), [t("agent 循环")])
            f.chip(x + 32, top + 320, "key", t("凭证（钥匙串）"))
            f.chip(x + 32, top + 364, "key", t("MCP 服务器"))
            f.arrow(f"M{x + 142},{top + 170} V{top + 198}", both=True)
            f.layer(vx + 30, top + 186, vw - 60, "exec", t("执行环境"), [t("代码执行")])
            f.chip(vx + 30, top + 296, "key", t("代理：只放行本会话令牌"), w=vw - 60)
            f.arrow(f"M{x + 254},{top + 240} H{vx + 28}")
            f.label(x + 306, top + 228, t("会话令牌"), "s")
            notes = [(True, t("虚拟机出错，只是一次工具调用失败")), (True, t("凭证留在宿主机，虚拟机只拿收窄、可吊销的令牌"))]
        for j, (ok, s) in enumerate(notes):
            ny = top + zh + 44 + j * 36
            f.mark(x + 12, ny - 6, ok)
            f.text(x + 34, ny, s, "b")
    return f.save("fig-5-cowork")


def fig_forces():
    f = Figure(910, t("图 4 · 决定部署位置的因素"), t("每个因素只拉动一部分，各部分因此被分开"),
               t("七个因素分别作用于某一层，或某两层之间的边界"), t("各因素的具体分析见第三节"))
    ry = 440
    f.layer(96, ry, 300, "access", t("接入层"))
    f.layer(560, ry, 300, "runtime", t("运行时"))
    f.layer(1168, ry, 300, "exec", t("执行环境"))
    f.layer(560, 222, 300, "model", t("模型服务"))
    f.arrow(f"M398,{ry + 24} H558", both=True)
    f.arrow(f"M862,{ry + 24} H1166")
    f.arrow(f"M710,{ry - 2} V272", both=True)
    # isolation boundary between runtime and execution
    bx = 1014
    f.line(bx, ry - 40, bx, ry + 88, ROSE, 2, dash=True)
    # forces above
    f.card(96, 318, 380, t("网络可达性"), [t("运行时要能访问模型服务")])
    f.arrow(f"M478,357 H704")
    f.card(944, 222, 524, t("安全隔离 · 故障隔离"), [t("凭证和审批权不与执行环境放在一起"), t("执行环境出错不连累运行时")])
    f.arrow(f"M{bx + 20},{328} L{bx + 2},{ry - 42}")
    # forces below
    by = 540
    for x, w, title, line, tx in ((96, 300, t("接入与身份"), t("拉向用户已经在用的地方"), 246),
                                 (560, 300, t("在线时长"), t("拉向常开的地方"), 710),
                                 (1168, 300, t("资源位置"), t("拉向资源所在的地方"), 1318)):
        f.card(x, by + 40, w, title, [line])
        f.arrow(f"M{tx},{by + 38} V{ry + 50}")
    # spanning forces
    sy = 720
    f.rect(96, sy, 1372, 100, PAPER, RULE, r=12)
    f.text(120, sy + 38, t("闲置成本"), "q")
    f.text(260, sy + 38, t("三部分的生命周期不同：运行时共享、执行环境按需创建、接入层随时断开"), "lab")
    f.text(120, sy + 76, t("合规"), "q")
    f.text(260, sy + 76, t("反方向的力：数据不能离开某个范围，就把包括模型在内的所有部分圈在里面"), "lab")
    return f.save("fig-4-forces")


def fig_reverse():
    f = Figure(620, t("图 7 · 控制方向反转"), t("运行时在云端时，最终的权限检查要放在本地"),
               t("连接由本地发起，指令由云端下发；云端运行时一旦被注入，本地检查是最后一道防线"),
               t("适用于形态 5，也适用于引子中的海外服务器方案"))
    top, zh = 200, 320
    f.zone(72, top, 700, zh, "device", t("用户的电脑"))
    f.zone(940, top, 588, zh, "cloud", t("云端"))
    f.layer(104, top + 80, 270, "exec", t("执行环境"), [t("浏览器、文件"), t("登录状态")])
    gx, gw = 470, 270
    f.rect(gx, top + 80, gw, 140, INDIGO_DEEP, r=12)
    f.text(gx + gw / 2, top + 138, t("权限检查"), "hs", "middle", "fill:#ffffff")
    f.text(gx + gw / 2, top + 170, t("最终在本地执行"), "lab", "middle", "fill:#c7d2fe")
    f.layer(1010, top + 80, 448, "runtime", t("运行时"), [t("接收任务、调用模型"), t("发出工具调用")])
    f.chip(1010, top + 240, "key", t("可能被提示注入"))
    f.arrow(f"M742,{top + 110} H1008")
    f.label(875, top + 96, t("① 本地发起出站连接"))
    f.arrow(f"M1008,{top + 190} H744", dash=True)
    f.label(875, top + 176, t("② 下发指令"))
    f.arrow(f"M468,{top + 150} H376")
    f.label(422, top + 136, t("③ 放行"), "s")
    f.text(420, top + zh - 28, t("不需要开放入站端口，设备没有公网地址也能连通"), "s", "middle")
    return f.save("fig-7-reverse")


def strip(f, x, y, boxes, bw=176, bh=90, gap=30):
    """A row of places with chips inside, joined by arrows. boxes: (kind, title, chips, link_to_next)."""
    for i, (kind, title, items, link) in enumerate(boxes):
        bx = x + i * (bw + gap)
        f.zone(bx, y, bw, bh, kind, "")
        f.text(bx + bw / 2, y + 26, title, "s", "middle")
        f.chips(bx + 8, y + 40, bw - 16, [(k, t(l), d) for k, l, d in items], h=28, gap=6)
        if i < len(boxes) - 1:
            ay = y + bh / 2
            f.arrow(f"M{bx + bw + 4},{ay} H{bx + bw + gap - 4}", dash=(link == "tunnel"), both=(link == "tunnel"))
    return x + len(boxes) * (bw + gap) - gap


def fig_china():
    f = Figure(840, t("图 6 · 中国大陆"), t("同一个软件，在国内常被部署成另一种形态"),
               t("各因素的权重变了：网络可达性和合规的分量更重"), t("详见第四节"))
    lx, cx1, cx2 = PAD, 320, 935
    f.line(920, 180, 920, 770, RULE, 2)
    f.text(cx1, 206, t("设计初衷 / 海外常见"), "h")
    f.text(cx2, 206, t("国内常见"), "h")
    f.line(PAD, 226, W - PAD, 226, RULE, 2)
    # OpenClaw
    y = 262
    f.text(lx, y + 50, "OpenClaw", "h")
    f.text(lx, y + 80, t("本地优先的 agent 网关"), "s")
    strip(f, cx1, y, [("device", t("手机 · 聊天软件"), [("access", "接入", 0)], "->"),
                      ("device", t("家里的 Mac mini"), [("runtime", "运行时", 0), ("exec", "执行", 0)], "->"),
                      ("cloud", t("模型服务"), [("model", "模型", 0)], "")])
    strip(f, cx2, y, [("device", t("飞书 / 钉钉 / 微信"), [("access", "接入", 0)], "->"),
                      ("cloud", t("云厂商轻量服务器"), [("runtime", "运行时", 0), ("exec", "执行", 0)], "->"),
                      ("cloud", t("模型服务"), [("model", "模型", 0)], "")])
    f.text(cx2, y + 124, t("变成形态 7；网关端口从家庭网络暴露到公网"), "s")
    f.line(PAD, 440, W - PAD, 440, RULE, 2)
    # Claude Code
    y = 476
    f.text(lx, y + 120, "Claude Code", "h")
    f.text(lx, y + 150, t("本地编码 agent"), "s")
    strip(f, cx1, y + 96, [("device", t("用户电脑"), [("access", "接入", 0), ("runtime", "运行时", 0), ("exec", "执行", 0)], "->"),
                           ("cloud", "Anthropic", [("model", "模型", 0)], "")], bw=260)
    f.text(cx2, y + 4, t("a · 保留运行时，替换模型"), "b")
    strip(f, cx2, y + 18, [("device", t("用户电脑"), [("access", "接入", 0), ("runtime", "运行时", 0), ("exec", "执行", 0)], "->"),
                           ("cloud", t("国产模型"), [("model", "模型", 0)], "")], bw=260)
    f.text(cx2, y + 150, t("b · 运行时在海外服务器（引子）"), "b")
    strip(f, cx2, y + 164, [("device", t("用户电脑"), [("access", "接入", 0), ("exec", "执行", 0)], "tunnel"),
                            ("cloud", t("海外服务器"), [("runtime", "运行时", 0)], "->"),
                            ("cloud", "Anthropic", [("model", "模型", 0)], "")])
    return f.save("fig-6-china")


def fig_decide():
    f = Figure(1060, t("图 8 · 选型"), t("四个问题，选出部署形态"),
               t("从上往下回答；「是」向右，「否」向下"),
               t("企业场景把接入层换成企业 IM 即为形态 7；通用桌面助手可同时连接多个执行环境（形态 8）"))
    qx, qw, rx, rw, qh = 120, 640, 900, 628, 64

    def q(y, s):
        f.rect(qx, y, qw, qh, "#ffffff", INDIGO, r=12)
        f.text(qx + qw / 2, y + 40, s, "q", "middle")

    def leaf(x, y, w, title, note):
        f.rect(x, y, w, 76, TINT, LINE, r=12)
        f.text(x + 20, y + 32, title, "q")
        f.text(x + 20, y + 58, note, "s")

    def yes(y):
        f.arrow(f"M{qx + qw + 2},{y + qh / 2} H{rx - 4}", color="indigo")
        f.label((qx + qw + rx) / 2, y + qh / 2 - 12, t("是"), "s")

    def no(y0, y1):
        f.arrow(f"M{qx + qw / 2},{y0 + qh + 2} V{y1 - 4}")
        f.label(qx + qw / 2 + 28, (y0 + qh + y1) / 2 + 6, t("否"), "s", bg=False)

    ys = [200, 330, 460, 720]
    q(ys[0], t("数据必须留在企业内网？"))
    yes(ys[0]); leaf(rx, ys[0] - 6, rw, t("私有化部署"), t("接入层、运行时、执行环境和模型都在内网"))
    no(ys[0], ys[1])
    q(ys[1], t("资源能复制到云端，且任务要并行或离线继续？"))
    yes(ys[1]); leaf(rx, ys[1] - 6, rw, t("4  云端托管"), t("换来并行和离线继续；付出本地资源和控制权"))
    no(ys[1], ys[2])
    q(ys[2], t("任务比设备在线时间长，或要从手机派任务？"))
    yes(ys[2])
    f.rect(rx, ys[2], rw, qh, "#ffffff", INDIGO, r=12)
    f.text(rx + rw / 2, ys[2] + 40, t("常开的运行时由谁提供？"), "q", "middle")
    lw = (rw - 20) / 2
    for i, (who, title, note) in enumerate(((t("用户自己"), t("6  远程接入 + 本地运行时"), t("自己维护一台常开设备")),
                                            (t("厂商"), t("5  云端运行时 + 本地执行"), t("权限检查放在本地")))):
        lx = rx + i * (lw + 20)
        f.arrow(f"M{lx + lw / 2},{ys[2] + qh + 2} V{ys[2] + qh + 56}")
        f.label(lx + lw / 2, ys[2] + qh + 34, who, "s")
        f.rect(lx, ys[2] + qh + 60, lw, 76, TINT, LINE, r=12)
        f.text(lx + 20, ys[2] + qh + 92, title, "q")
        f.text(lx + 20, ys[2] + qh + 118, note, "s")
    no(ys[2], ys[3])
    q(ys[3], t("希望 agent 自动运行，不逐条审批？"))
    yes(ys[3]); leaf(rx, ys[3] - 6, rw, t("3  本地运行时 + 隔离执行"), t("凭证留在隔离区外；执行环境出错不影响运行时"))
    no(ys[3], ys[3] + 130)
    leaf(qx, ys[3] + 130, qw, t("1  全本地"), t("零部署、零额外延迟；设备离线任务就停"))
    return f.save("fig-8-decide")


if __name__ == "__main__":
    for fn in (fig_intro, fig_parts, fig_forms, fig_cowork, fig_forces, fig_reverse, fig_china, fig_decide):
        print(fn())
