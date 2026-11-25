# 待实现功能

尚未实现的功能，按优先级排列，每项分别写出 ollupi（引擎）和 desktop（界面、主进程、sidecar）各自要改什么。原则：逻辑放在拥有它的那一层，desktop 只做展示和装配。实现后从这里删掉，并写进[功能清单](/zh/reference/features)。

## 总览

| # | 功能 | 优先级 | ollupi | desktop |
|---|---|---|---|---|
| 1 | 编辑历史消息、分叉、回滚 | P1 | ✔ | ✔ |
| 2 | 云沙箱提供者 | P2 | ✔ | ✔ |
| 3 | Linux / Windows | P3 | ✔ | ✔ |
| 4 | Apple 公证 | P3 | | ✔ |
| 5 | 远程访问 | P3 | ✔ | ✔ |

## P1

### 1. 编辑历史消息、分叉、回滚

编辑最新一条消息已经做了（见[功能清单](/zh/reference/features)），剩下的是更早的消息。

- ollupi
  - `thread/fork`：从某个 item 复制出新会话
  - 编辑某条用户消息 = 从它之前分叉，再以新内容开新一轮
  - 回滚只回滚会话记录，不撤销已执行的工具副作用，要在协议里写明
- desktop
  - 消息上的"编辑"、"从这里分叉"
  - 分叉出的会话标明来源

## P2

### 2. 云沙箱提供者

执行环境、沙箱提供者的接口和桌面端的环境对话框都已经做了（见[功能清单](/zh/reference/features)），但还没有接入任何云沙箱（E2B、Daytona 等），后端只提供这台电脑。接一家就是写一个提供者，放进 `host.Config.Sandboxes`，见[云沙箱](/zh/integrate/extend#云沙箱)。

- ollupi
  - 实现一家的 `sandbox.Provider`：`Open` 建出或找回沙箱，用 `Keep` 记下沙箱的 ID；`Remove` 删掉它；机器实现 `sandbox.Machine`，用 `sandbox.Remote` 包成 Box
  - 沙箱的网络规则、休眠和唤醒由提供者负责
- desktop
  - sidecar 在 `Sandboxes` 里加上这个提供者，和这台机器并列
  - 环境对话框在后端提供不止一种沙箱时已经会出现选择；还要能填提供者的设置（`environment/add` 的 `config`，比如模板、地区）

## P3

### 3. Linux / Windows

沙箱依赖 macOS Seatbelt。

- ollupi
  - `pkg/sandbox` 加 Linux 实现（bubblewrap / Landlock + seccomp）；Windows 方案另议
  - 无法强制沙箱的平台必须明确报告，审批策略据此收紧
- desktop
  - electron-builder 增加 Linux / Windows 目标，sidecar 多平台构建
  - 自动更新支持对应安装包

### 4. Apple 公证

- desktop
  - 发布流程加签名和公证，用户首次打开不再被拦下

### 5. 远程访问

网关已有令牌认证、允许的主机名，监听由宿主传入；每个用户最多四条连接，每条都收到全部事件。还缺：

- ollupi
  - 监听非本机地址时要求 TLS
  - 协议里写明：多个客户端同时连接时，审批和回答只处理第一个
- desktop
  - 设置里开启远程访问，显示地址和配对码
  - 移动端客户端另立项目
