# 待实现功能

尚未实现的功能，按优先级排列，每项分别写出 ollupi（引擎）和 desktop（界面、主进程、sidecar）各自要改什么。原则：逻辑放在拥有它的那一层，desktop 只做展示和装配。实现后从这里删掉，并写进[功能清单](/zh/reference/features)。

## 总览

| # | 功能 | 优先级 | ollupi | desktop |
|---|---|---|---|---|
| 1 | 编辑消息、分叉、回滚 | P1 | ✔ | ✔ |
| 2 | Linux / Windows | P3 | ✔ | ✔ |
| 3 | Apple 公证 | P3 | | ✔ |
| 4 | 远程访问 | P3 | ✔ | ✔ |

## P1

### 1. 编辑消息、分叉、回滚

- ollupi
  - `thread/fork`：从某个 item 复制出新会话
  - 编辑某条用户消息 = 从它之前分叉，再以新内容开新一轮
  - 回滚只回滚会话记录，不撤销已执行的工具副作用，要在协议里写明
- desktop
  - 消息上的"编辑"、"从这里分叉"
  - 分叉出的会话标明来源

## P3

### 2. Linux / Windows

沙箱依赖 macOS Seatbelt。

- ollupi
  - `pkg/sandbox` 加 Linux 实现（bubblewrap / Landlock + seccomp）；Windows 方案另议
  - 无法强制沙箱的平台必须明确报告，审批策略据此收紧
- desktop
  - electron-builder 增加 Linux / Windows 目标，sidecar 多平台构建
  - 自动更新支持对应安装包

### 3. Apple 公证

- desktop
  - 发布流程加签名和公证，用户首次打开不再被拦下

### 4. 远程访问

网关只给本机界面用。

- ollupi
  - 网关支持监听非本机地址，要求 token 认证和 TLS
  - 多个客户端同时连接时，审批和回答只处理第一个
- desktop
  - 设置里开启远程访问，显示地址和配对码
  - 移动端客户端另立项目
