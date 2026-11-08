# 内置浏览器

内置浏览器是应用自带的 Chromium 标签页，放在会话右侧，代理和用户共用。代理能打开网页、读内容、点击、输入；用户看得到它在做什么，也能随时接手，比如登录一个代理进不去的站点。

浏览器属于桌面端，不属于引擎。sidecar 只提供工具的名称和描述，把调用转发给主进程。主进程拥有全部 `WebContentsView`，页面脚本也在那里运行。

## 标签页归属

每个会话有一组标签页，由主进程的 `AgentBrowser` 按会话 ID 保管。

```ts
interface Strip {
  thread: string
  tabs: WebContentsView[]
  active: WebContentsView | undefined
}
```

| 规则 | 实现 |
|---|---|
| 代理在当前显示的标签页里操作 | 所有动作都作用于 `strip.active` |
| 用户切换标签页，代理跟着换 | `select` 改的就是 `active` |
| 页面打开新窗口时开成新标签页 | `setWindowOpenHandler` 拒绝窗口，在同一个会话里 `newTab`，只开 http 和 https |
| 点击打开新标签页后代理留在新页 | `newTab` 把新标签设为 `active`，`call` 最后读的是 `active` |
| 关闭当前标签页 | 下一个标签顶上，没有下一个时取最后一个 |
| 子代理 | 工具调用带的是子代理自己的会话 ID，所以它有自己的标签页 |

**草稿的标签页。** 草稿页的会话还不存在，标签页挂在固定的 ID `draft` 下。发出第一条消息时，`startThread` 在第一轮开始之前调用 `handOver('draft', threadId)`，标签页移到这个会话。

**显示。** 同一时间最多一个标签页可见。`shown` 记录当前显示哪个会话和在哪块区域。`layAll` 遍历所有标签，只把那个会话的 `active` 设为可见并放到指定位置，其余全部隐藏。隐藏的标签页继续运行。

**标签页的生命周期。** 它们只活在内存里，随窗口存在，不跨应用重启。后端重启不影响标签页。窗口隐藏时标签页还在。窗口已不存在时打开标签页会被拒绝。

## 视图的放置

网页不是 DOM 的一部分，是主进程盖在窗口上的原生视图。`BrowserPanel` 量出自己的区域，告诉主进程放在哪里：

```ts
const r = el.getBoundingClientRect()
void desktop.browser.place(thread, { x: r.left, y: r.top, width: r.width, height: r.height })
```

`ResizeObserver` 和窗口 `resize` 时重新上报。这几种情况隐藏视图，否则它会盖住或抢走指针：

- 页面还没打开，这时面板显示说明文字。
- 拖动面板边缘。
- 收藏列表或地址补全列表打开，这两个是 DOM 浮层，画在视图下面。
- 面板关闭或切换到别的会话。

## 工具调用的路径

```mermaid
sequenceDiagram
  participant E as 引擎
  participant S as sidecar browser
  participant P as 主进程端点
  participant B as AgentBrowser
  participant W as WebContents
  E->>S: PermissionContent(click, ref)
  S->>P: POST /describe
  P->>B: describe(thread, action, args)
  B->>W: describeScript
  W-->>S: host, text
  Note over E: 用 host 匹配规则，需要时审批
  E->>S: Invoke(browser_click)
  S->>P: POST /call
  P->>B: call(thread, action, args)
  B->>W: 输入事件或页面脚本
  B->>W: snapshotScript
  W-->>S: text
  S-->>E: 工具结果
```

端点是主进程在 `127.0.0.1` 随机端口上开的 HTTP 服务，后端启动之前就开好。地址和令牌通过 `OLLUPI_BROWSER_URL`、`OLLUPI_BROWSER_TOKEN` 给 sidecar，每次启动和每次配置校验都带上。令牌用 `timingSafeEqual` 比较。

请求体：

```json
{"thread": "<会话 ID>", "action": "click", "arguments": {"ref": "e12"}}
```

| 状态码 | 含义 | sidecar 怎么处理 |
|---|---|---|
| 200 | `/call` 回 `{text}`，`/describe` 回 `{host, text}` | 正常 |
| 400 | 请求体不对 | 工具错误 |
| 401 | 令牌不对 | 工具错误 |
| 404 / 405 | 路径或方法不对 | 工具错误 |
| 422 | `Refusal`，比如 ref 过期、没有打开的页面，`{error}` 是给代理看的文字 | 作为工具输出返回，代理能读到并调整 |
| 500 | 其他异常 | 工具错误 |

sidecar 的 HTTP 超时是 90 秒，够页面在动作之后加载完。主进程不回应时报 `the app does not answer`。

## 工具

工具名是 `browser_<action>`，提供方名 `browser`，所以 MCP 服务器不能用这个名字（配置校验会拒绝）。所有工具都标了 `Serial: true`：同一会话的调用共用一个活动标签页，不能并行。

| 工具 | 参数 | 只读 | 开放世界 | 有权限内容 |
|---|---|---|---|---|
| `browser_navigate` | `url` | 是 | 是 | 是 |
| `browser_snapshot` | | 是 | 否 | 否 |
| `browser_click` | `ref` | 否 | 是 | 是 |
| `browser_type` | `ref`、`text`、`submit` | 否 | 是 | 是 |
| `browser_press_key` | `key` | 否 | 是 | 是 |
| `browser_scroll` | `direction`（`down`、`up`） | 是 | 否 | 否 |
| `browser_back` | | 是 | 是 | 是 |

### 按网站审批

有权限内容的工具在审批前调用 `/describe`，得到操作的文字描述和标签页的 host。host 是权限内容的匹配值，所以规则和审批都按网站走。引擎在已批准的调用执行前再算一遍，标签页换了站点就重新询问。

`navigate` 的 host 取目标地址，其余取当前页面。描述文字举例：

| 动作 | 描述 |
|---|---|
| `navigate` | `Open https://example.com/` |
| `click` | `Click button "Sign in" on example.com` |
| `type` | `Type "hello" into textbox "Search" and press Enter on example.com` |
| `press_key` | `Press Enter on example.com` |
| `back` | `Go back from example.com` |

`describe` 里 ref 过期，或 `back` 没有更早的页面，直接拒绝。

审批策略由工具注解决定（[权限](/engine/permissions)）：

| 策略 | 需要审批的工具 |
|---|---|
| 严格（`untrusted`） | 非只读或开放世界：`navigate`、`click`、`type`、`press_key`、`back` |
| 适中（`on-request`） | 非只读：`click`、`type`、`press_key` |
| 宽松（`never`） | 无 |

这张表是没有规则时的结果。allow、ask、deny 规则可以改变它。

### 动作的实现

| 动作 | 怎么做 |
|---|---|
| `navigate` | `normalize` 地址后 `loadURL`，没有标签页时新建。加载失败不算错，页面显示错误页 |
| `click` | 标签页在屏幕上时，`locateScript` 滚到元素中心，用 `sendInputEvent` 发真实的鼠标事件，页面看到的是人的点击。不在屏幕上时收不到输入事件，改用 DOM 的 `el.click()` |
| `type` | `focusScript` 聚焦并全选，`insertText` 替换内容，`submit` 时再按 Enter |
| `press_key` | `sendInputEvent` 发 `keyDown`、`keyUp`，单个字符时加 `char` |
| `scroll` | `window.scrollBy`，一屏的 80% |
| `back` | `navigationHistory.goBack` |

只有 `click` 有屏幕外的回退，`press_key` 和 `submit` 的 Enter 总是走 `sendInputEvent`。

`call` 开始时发 `used` 事件。渲染进程收到后，如果这个会话正在屏幕上，打开浏览器面板，让用户看到代理在做什么。

## Snapshot 格式

每个动作都以页面文本作答，`snapshot` 只是不做动作直接读。`read` 先等 200 毫秒，页面还在加载时再等 `did-stop-loading`，最多 15 秒。

返回的文本是标题、地址和快照：

```
Example Domain
https://example.com/

- heading "Example Domain" [level=1]
- text "This domain is for use in documentation examples."
  - link "Learn more" [ref=e1] -> https://iana.org/domains/example
```

页面为空时写 `(the page shows nothing)`。

`snapshotScript` 从 `document.body` 开始按文档顺序遍历，只读显示出来的内容：

| 节点 | 输出 |
|---|---|
| 可交互元素 | `- <角色> "<名称>" [ref=eN]`，不再往下走 |
| `h1` 到 `h6` | `- heading "<文字>" [level=N]`，最长 160 字符 |
| 有 `alt` 的 `img` | `- img "<alt>"` |
| 有直接文本的元素 | `- text "<文字>"`，最长 300 字符，子元素缩进一级 |
| `script`、`style`、`noscript`、`template`、`svg`、`iframe` | 跳过 |
| Shadow DOM | 进入 `shadowRoot` 的子元素 |

**可交互元素**包括 `a[href]`、`button`、非隐藏的 `input`、`textarea`、`select`、`summary`、`contenteditable`，以及 `role` 为 button、link、checkbox、radio、switch、tab、menuitem、option、combobox、textbox、searchbox 的元素。

**角色**优先取 `role` 属性，否则按标签推断。**名称**依次取 `aria-label`、`aria-labelledby`、关联的 `label`、文字、`placeholder`、`title`、`alt`、`value`，截到 100 字符。

**附加信息**：

- 链接后加 `-> <href>`，截到 80 字符。
- 文本框的内容写成 `value="..."`。密码框只写 `value=(hidden)`，内容不进快照。
- `checked`、`disabled` 标在行尾。
- `select` 写当前选项。

**隐藏判断**：`aria-hidden="true"`、`display: none`、`visibility: hidden`，或宽高都是 0（`display: contents` 除外）。

**长度**：上限 40000 字符（`SNAPSHOT_LIMIT`，注释说约 1 万 token）。超过时结尾写 `[the page goes on; scroll and take another snapshot to read more]`。缩进最多 12 级。

### ref 和隔离世界

ref 是这次快照的元素编号，`e1`、`e2`。`window.__ollupiRefs` 是 ref 到元素的 Map，下次快照时重建。

所有页面脚本都用 `executeJavaScriptInIsolatedWorld` 跑在 1001 号隔离世界（`WORLD`）。页面自己的脚本看不到也改不了它，它能看到页面的 DOM。

元素已从页面移除时（`isConnected` 为假），动作报 `no element eN on the page now; take a new snapshot`，代理读到后重新快照。ref 必须匹配 `^e\d+$`。

## 地址

`normalize` 处理用户和代理输入的地址：

- 没有协议时，`localhost`、`127.0.0.1`、`[::1]` 补 `http://`，其余补 `https://`。
- 只开 http 和 https，别的协议拒绝。主进程能加载页面自己不能加载的东西（比如 `file:`），所以无论谁发起都不放行。

## 登录分区

所有标签页共用一个分区 `persist:browser`，和应用自身的 session 分开，并持久化。登录状态存在 `~/Library/Application Support/Ollupi/Partitions/browser`，不和 Chrome 共用。

| 配置 | 值 | 原因 |
|---|---|---|
| User-Agent | Chromium 的默认值去掉 `Electron/...` 和应用名 | Google 登录这类站点会拒绝标着嵌入式浏览器的 UA |
| 设备权限 | 一律拒绝 | `setPermissionRequestHandler` 回 `false` |
| 下载 | 全部取消 | `will-download` 里 `item.cancel()` |
| `webPreferences` | `sandbox`、`contextIsolation` 开，`nodeIntegration` 关 | |

这些在第一次创建标签页时配置一次。

## 历史

`History` 记下每个标签页打开过的网页，用户和代理打开的都算。文件是 `~/Library/Application Support/Ollupi/history.json`。

- 一次访问是标签页到达另一个地址：`did-navigate` 和主框架的 `did-navigate-in-page`。刷新或页面把地址改成原样不算。
- 每个网页一条：`url`、`title`、`visits`、`last`。
- 最多 5000 条（`LIMIT`），超过时删掉最久没访问的。
- 改动 1 秒后批量写入（`SAVE_DELAY`），退出时 `flush`。
- 标题后到时用 `titled` 事件补上。只有页面显式设置的标题才算。

文件写入经过 `.tmp` 再改名，崩溃不会留下半个文件。文件读不了时抛错，不当成空，否则下一次保存会覆盖原内容。这条规则在 `readKept` 里，收藏也用它。

在 **设置 → 通用** 能看到网页数并清除。

## 收藏

`bookmarks.json` 存用户自己的收藏。加入时放到最前，已存在的移到最前并更新标题。

Chrome 的收藏只读，列出时现读：

1. 读 `~/Library/Application Support/Google/Chrome/Local State` 的 `profile.info_cache` 得到全部个人资料和显示名。
2. 读每个个人资料的 `Bookmarks` 文件，它是纯 JSON，Chrome 一直在写，所以只读不改。
3. 只留 http 和 https，记下所在的文件夹路径。

读不到时返回空，Chrome 不是必须的。

## 地址栏补全

`suggest` 对输入返回最多 8 条（`LIMIT`），来源是历史和收藏（含 Chrome 的）。

**匹配**：地址或标题要包含输入的每个词。比较时地址用 `bare` 去掉协议、`www.` 和单独的结尾斜杠。

**排序**：

| 层 | 条件 |
|---|---|
| 2 | 地址以输入开头 |
| 1 | 每个词都是地址或标题里某个词的开头 |
| 0 | 其余 |

同层内按分数排：`visits × 时效系数 + (已收藏 ? 1 : 0)`，再按最近访问。

| 距上次访问 | 系数 |
|---|---|
| 4 天内 | 1 |
| 14 天内 | 0.7 |
| 31 天内 | 0.5 |
| 90 天内 | 0.3 |
| 更久 | 0.1 |

**就地补全**：第一条在第 2 层时补进输入框，补上的部分处于选中状态，下一次按键替换它。还在输入站点名时只补到站点，回车打开站点首页。删除字符时不补全。

**键盘**：方向键选择，回车打开，Esc 先收起列表，再按一次放弃输入。

输入过程中只有最新的一次询问生效（`asked` 计数），避免旧结果盖掉新结果。

## 代码位置

| 位置 | 职责 |
|---|---|
| ollupi-desktop `sidecar/internal/browser/browser.go` | 工具定义和转发 |
| ollupi-desktop `apps/desktop/src/main/browser/browser.ts` | `AgentBrowser`：标签页、动作、分区配置 |
| ollupi-desktop `apps/desktop/src/main/browser/page.ts` | 页面内脚本：快照、定位、点击、聚焦 |
| ollupi-desktop `apps/desktop/src/main/browser/endpoint.ts` | 回环 HTTP 端点 |
| ollupi-desktop `apps/desktop/src/main/browser/address.ts` | 地址规范化 |
| ollupi-desktop `apps/desktop/src/main/browser/history.ts` | 历史记录 |
| ollupi-desktop `apps/desktop/src/main/browser/bookmarks.ts` | 收藏和 Chrome 收藏 |
| ollupi-desktop `apps/desktop/src/main/browser/suggest.ts` | 地址栏补全 |
| ollupi-desktop `apps/desktop/src/main/browser/file.ts` | JSON 文件的安全读写 |
| ollupi-desktop `apps/desktop/src/renderer/src/views/conversation/BrowserPanel.tsx` | 面板、标签栏、地址栏 |
