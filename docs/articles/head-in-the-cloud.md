---
title: Head in the Cloud, Hands at Home
description: Why an agent's access layer, runtime and execution environment end up in different places. Nine topologies, seven forces, the engineering problems at each boundary, and which topology fits which job.
outline: [2, 3]
---

# Head in the Cloud, Hands at Home

*Why the parts of an agent end up in different places*

November 8, 2026 · [中文版](/zh/articles/head-in-the-cloud)

## Opening

Anthropic does not offer Claude in mainland China. In September 2025 it went further and barred companies controlled from China, wherever they are registered.

Some developers in China who want Claude Code found a workaround. They rent a server overseas and run Claude Code there, where the model API is reachable. But their code, files and browser are still on their own computer, so they tunnel that computer back to the overseas server.

The result: the agent's runtime sits on the other side of an ocean, its execution environment sits on the developer's desk, and the two are joined by a tunnel the user built themselves.

![The runtime is overseas, the execution environment is on the desk](/figures/head-in-the-cloud/fig-1-intro.en.svg)

A Tang dynasty poem has the line "clouds in the blue sky, water in the vase": everything in its proper place. This agent is the opposite. Its head is in the cloud, its hands are at home, and no part is where you would expect it.

It sounds like a hack forced by unusual circumstances. It isn't. Manus lets its cloud agent drive the user's own browser, and the structure is the same. Anthropic's Cowork once put the whole agent inside a VM and later moved the agent loop out. The parts of an agent have different needs about where they run, so split placement is the norm, not the exception.

This article breaks an agent into its parts, maps the common deployment topologies, and looks at the forces that decide where each part runs, with a separate section on mainland China. It ends with a verdict: which topology fits which job, and what each one buys you.

## 1. The parts of an agent

An agent is usually described as three layers.

**Access layer.** Where the user talks to the agent: a desktop app, a web page, a mobile app, a terminal, or a bot in Telegram, WhatsApp, Slack, WeChat, Feishu or DingTalk.

**Runtime.** The agent loop and its orchestration. It builds the context, calls the model, parses tool calls, checks permissions and asks for approval, schedules subtasks, and handles retries and interruptions.

**Execution environment.** Where tools actually run: a shell, a file system, a browser, desktop apps, databases, intranet services. It can be the user's own computer, a local container, VM or OS-level sandbox, or a sandbox in the cloud.

Two more parts matter for deployment.

**Model service.** Unless you run a local model, it is always remote. So no agent is fully local: whatever is read into the context is sent to the model. "Local execution" really means the raw resources stay local and only what gets read leaves.

**Session state.** The transcript, pending work, approvals and memory. Where state lives decides who can continue a session after a disconnect, a device switch or a crash. Claude Code's Remote Control lets you drive a terminal session on your computer from your phone. Execution never leaves the computer, but while connected the transcript is stored on Anthropic's servers, and that copy is what the phone works from.

![An agent has five parts and three boundaries](/figures/head-in-the-cloud/fig-2-parts.en.svg)

Each of these five parts can be placed somewhere different. Here are the combinations that show up in practice.

## 2. Nine topologies

Figure 3 classifies topologies by where each part runs, not by product category. One product can support several.

![Nine topologies](/figures/head-in-the-cloud/fig-3-forms.en.svg)

A few of them deserve a closer look.

**Topology 2 versus topology 3.** Both use isolation, but they isolate different things (compared in figure 5). Topology 2 puts the runtime and the execution environment in the same box, so API keys, approval logic and session state share an environment with code the model wrote. If the model is steered by injected instructions (prompt injection), it can run commands, and so it can read the keys. Topology 3 isolates only execution. The runtime stays outside the box and holds the credentials and the approval decision.

Topology 3 is only as safe as one assumption: the logic that decides whether something may cross the boundary must not be swayed by untrusted input. Anthropic says so about Claude Code: a privileged process outside the sandbox decides per command whether to sandbox it, and a persuasive injected prompt or a tired approval click can get a command run outside the sandbox.

**Topology 5: cloud runtime, local execution.** This exists because some resources can't be copied to the cloud. A repository can be cloned. A logged-in session, a two-factor device, a local IP address, an intranet behind a VPN, or software installed only on the user's machine cannot. Manus already had a cloud browser, then shipped the Browser Operator extension to drive the user's own browser. Manus recommends it for sites where the user is already logged in and keeps the cloud browser for everything else.

**Topology 6: a home node the user runs.** OpenClaw is a self-hosted gateway that connects more than twenty chat channels, including WhatsApp, Telegram, iMessage and Slack, to agent sessions on the user's own machine. Its docs recommend an always-on machine such as a Mac mini or a VPS. Two needs meet here: the runtime has to stay online, and execution has to reach the user's own files and accounts. Claude Code's Remote Control has the same shape. The local session only makes outbound HTTPS requests and opens no inbound port; it registers with the server and polls for work, and the phone or browser is just a client of that local session.

**Topology 8: more than one execution environment.** In one agent, file reads and writes may happen directly on the host through a mounted folder, shell commands run in a VM, pages that need a login open in the user's browser, and heavy compute goes to a cloud sandbox. Different tools depend on different resources, so the execution environment should be designed as plural from the start.

**Topology 9: session migration.** Claude Code can pull a cloud session from its web version into the local terminal with `claude --teleport`, and the desktop app can hand a local session to the cloud. The runtime changes place; the session carries on.

## 3. The forces that decide placement

I count seven forces. Each acts mainly on one part, or on the boundary between two, which is why the parts get pulled apart.

![Each force pulls on one part, so the parts come apart](/figures/head-in-the-cloud/fig-4-forces.en.svg)

### Resource location: execution goes to the resources

Wherever the agent's resources are, the execution environment has to be there too. The question is whether those resources can be copied.

Copyable resources, such as repositories, public data and packages, can move to the cloud. That is why coding agents were the first to become cloud-hosted: clone the repo, work in the cloud, open a pull request.

Resources that can't be copied, such as logged-in sessions, device identity, intranet access, local software, attached hardware, and the many private files users won't upload, keep execution local. Topologies 5 and 6 both come from here.

### Uptime: the runtime goes where the power stays on

Agent tasks keep getting longer. They can run for hours and stop midway to wait for a human. User devices are not always on: laptops close and phones kill background apps.

Once a task outlives the device, the runtime has to move somewhere that stays on: a vendor's cloud (topology 4) or the user's own always-on machine (topology 6).

### Security isolation: keys and approvals stay away from execution

Model output is untrusted, so execution needs isolation. That much is settled. The next question is what must not sit next to execution. The answer is credentials and the power to approve.

Describing Claude Code on the web, Anthropic writes that sensitive credentials such as git credentials and signing keys are never inside the sandbox. The git client in the sandbox holds only a scoped credential for a proxy service. The proxy checks the branch and the destination repository before performing the real operation. Cowork works the same way: credentials stay in the host keychain, and the VM gets a per-session token that is scoped down and can be revoked on its own.

This force separates the runtime from execution, and it is the main reason topology 2 gives way to topology 3.

### Fault isolation: when execution fails, the runtime keeps going

Cowork is the clearest example.

Cowork is a desktop agent. At first the whole agent ran inside a local VM, agent loop and code execution alike: topology 2. Later the team moved the agent loop to the host and left only code execution in the VM: topology 3. Anthropic's reason was that any failure during VM startup made Cowork unusable, while a loop outside the VM can still answer the user and help debug. Around the same time, local MCP servers moved out of the VM too. Inside, they were harder to audit, broke on VM updates, and some needed to talk to local processes such as databases, which only works on the host. Security barely changed, because code still runs in the VM.

![Cowork moved the agent loop out of the VM](/figures/head-in-the-cloud/fig-5-cowork.en.svg)

If the runtime and execution share a failure domain (a set of things that fail together), an execution failure is an agent failure. A VM that won't boot, a container out of memory, a sandbox service timing out: the user sees the same frozen screen. Separated, an execution failure is one failed tool call. The runtime can tell the user, retry, switch to another execution environment, or ask for help.

The design rule that follows: an execution failure should be an event the runtime handles, never a failure of the runtime itself.

### Idle cost: agents mostly wait

An agent session is idle most of the time. It waits for the model, waits for tools, and mostly waits for the user to come back. Give every session its own always-on container and most of the compute pays for waiting.

This force is strongest in the cloud, and it gives each part its own lifecycle. The runtime becomes a stateless, multi-tenant service: state lives in a database and any free process picks the session up. Execution environments are created on demand, suspended, and restored from snapshots. Clients disconnect and reconnect at will. Bind all three together and you pay for the longest-lived one.

### Access and identity: the access layer goes where users already are

The access layer cares only about where the user is.

The phone is the device people use most and the worst place to execute: the OS is restrictive, background work is limited, and there is no general file system. Chat apps are already installed, support push notifications, and in companies carry identity and the org chart. So the access layer is usually the first part to split off. Once it does, approval changes too: a synchronous dialog becomes an asynchronous message. The agent pauses, you get a notification on the train, you tap approve, and it carries on.

### Network reachability and compliance: the runtime must reach the model

The runtime has to reach both the model service and the execution environment. If a model is only reachable from a certain network or region, the runtime has to run there, even if the user and the resources are elsewhere. The overseas server in the opening is exactly this. So is a model that only exists on a company intranet.

Compliance pulls the other way. If data can't leave a boundary, every part, the model included, goes inside it.

### One more: who gets control

Placement isn't purely technical. A runtime in the vendor's cloud gives the vendor metering, model routing, the data and the cross-device experience, which suits its business. Open-source and self-hosted projects lean toward leaving the runtime with the user. Keep this in mind when you read a product's architecture, but it doesn't override the technical constraints above.

## 4. Mainland China

Mainland China hasn't produced new topologies. What differs is the weight of each force: network reachability and compliance count for far more than elsewhere. So the same software often ends up in a different topology there than it was designed for (figure 6).

![The same software often ships in a different topology in China](/figures/head-in-the-cloud/fig-6-china.en.svg)

### Runtime overseas, execution at home

The opening setup is topology 5 in structure, with a different cause. Manus-style products use topology 5 because some resources can't be copied to the cloud and the vendor wants the runtime there. In the overseas-server setup, the runtime is forced abroad because that is the only place the model is reachable, and execution has to stay local because that is where the user's resources are.

The striking part is that users split the runtime from execution on their own, with no vendor support. That boundary is real. It isn't a design preference of any one product.

The costs are just as clear. First, the overseas server holds both the model account's credentials and a live connection into the user's personal computer; compromise the server and the attacker can drive the computer. That is exactly the arrangement the security force warns against. Second, every tool call crosses a border and back, which hurts latency and reliability. Third, it violates the provider's regional policy, and the account can be banned at any time.

Companies do something similar. According to a July 2026 Financial Times report, some Chinese companies reached Claude through overseas entities, for example in Singapore, and through API access resold by cloud providers. Anthropic responded by watching for signals such as the computer's time zone and by going after the relay services that forward requests.

### The chat app is the identity system

Feishu, DingTalk and WeCom all offer official bot and app APIs. An agent connected through them gets the user's identity, department and document permissions for free. The IM platform maintains that information, so the agent doesn't need its own identity system. For a company, that is often harder to replace than the agent itself.

Personal WeChat long had no official bot API for personal accounts. Community solutions emulated the protocol or injected into the client and risked bans. In March 2026 Tencent started rolling out a WeChat ClawBot plugin: run one install command on the machine that runs OpenClaw, scan a QR code, and you can talk to your own agent inside WeChat. China's most-used chat app became an official access layer for a self-hosted agent. The runtime didn't move; it stays wherever the user runs OpenClaw.

### Local-first software, moved to the cloud

OpenClaw is designed to be local-first, on the user's own always-on machine (topology 6). After it took off in China in early 2026, Alibaba Cloud, Tencent Cloud, Huawei Cloud and other major providers shipped lightweight server images with OpenClaw preinstalled, deployable in one click and connected to Feishu, DingTalk, WeCom or QQ. Volcano Engine went further with a hosted version tightly integrated with Feishu.

So many OpenClaw instances in China run their runtime and execution on a cloud server with a Chinese chat app as the access layer. In practice that is topology 7.

Two details stand out. Deployment guides pick the server region by what it must reach: a domestic region for domestic chat apps, while some guides recommend an overseas region. That is network reachability choosing where the runtime lives. And some one-click setups open the SSH port and the gateway port to the public internet. A gateway designed to sit on a home network now faces the whole internet, and its security requirements change with it.

### Keep the runtime, swap the model

Another common move is to keep the runtime of an agent like Claude Code and swap in a Chinese model. Zhipu GLM, Kimi, DeepSeek, MiniMax and Qwen all offer endpoints compatible with Anthropic's API format, so switching means changing a base URL and a key.

The runtime and the model service are independently replaceable too. A well-designed agent runtime is becoming a general client that can talk to many vendors' models.

A related service is the third-party API relay that resells access to overseas models. The relay sees the full context: code, file contents, and any keys a user pasted in. Where the model service runs, and who operates it, is part of the security boundary.

### On-premises: everything inside the company network

The enterprise market goes the other way. Data-security and cross-border-data regulations, plus the push for domestic technology substitution (known as Xinchuang), lead many companies to require on-premises deployment: access layer, runtime, execution environment and model all inside the company network, usually with an open-weight Chinese model.

Here compliance outweighs every other force. It runs against the global drift of runtimes toward the cloud, but it follows the same logic.

### In short

Topology follows the weights of the forces. Change the weights and the same software lands in a different topology.

## 5. Engineering problems at each boundary

Once the parts are separated, function calls become calls across processes, machines and sometimes trust domains. Each boundary brings its own problems.

### Access layer to runtime: the session protocol

Clients can disconnect at any moment, so the session protocol must support resuming and multi-device sync: the phone and the desktop must see the same state of the same session. That means the runtime owns the state and persists it, and clients only display it. Approvals have to be durable objects that can be handled asynchronously, not callbacks tied to a connection, because the approver may show up hours later on another device.

### Runtime to execution: remote-call semantics

Local function calls don't get lost. Remote calls do. After a timeout, the runtime can't know whether the other side ran the call. For `ls` it doesn't matter; for a payment or a `git push` it does. So the runtime has to tell "not run" apart from "may have run", and know which tools are safe to retry.

File sync is the hardest part. Mount, sync or copy? Which copy is authoritative? How are conflicts resolved? Cowork mounts the user's chosen folder into the VM, in read-only, read-write, or read-write-no-delete mode. Mounting has traps: symlinks must be resolved before paths are validated, or a symlink inside the authorized folder can point outside it.

The execution environment's lifecycle also enters the latency budget. A sandbox cold start takes seconds; restoring a snapshot may be faster or slower. The user feels it as the wait before the agent's first action.

### Cloud runtime, local execution: inverted control

Normally a local program calls a cloud service. In topology 5 it is the reverse: the cloud sends instructions to the user's computer.

![When the runtime is in the cloud, enforce permissions locally](/figures/head-in-the-cloud/fig-7-reverse.en.svg)

The local side usually dials out and then polls or holds a long-lived connection, so no inbound port is needed and it works without a public IP. Remote Control and browser-extension agents both do this. It solves connectivity. It doesn't solve trust.

The real question is where permissions are enforced. If approvals and policy live only in the cloud runtime, the local side will execute whatever the cloud sends, and an injected cloud runtime leaves the local machine fully exposed. Analyzing the Manus browser extension, the security firm Mindgard found that it can read and write cookies and local storage, and that the user's consent lasts for the whole conversation.

The conclusion: when the runtime and execution sit in different trust domains, the final permission check must happen on the execution side. Execution has to be able to refuse on its own, not just trust that the runtime already checked.

The overseas-server setup from the opening falls under the same rule, with higher stakes, because the user built that connection and usually gave it no security design at all.

### Credentials: on the side that doesn't run untrusted code

Every new boundary raises the question again: which side holds the credentials? The best current practice is to keep real credentials on the side that doesn't run untrusted code, give execution only scoped, revocable tokens, and let a proxy on the boundary perform the real operation.

Cowork also runs a proxy inside the VM that intercepts requests to the Anthropic API and passes only those carrying the VM's own session token. It defends against a specific attack: a malicious file in the workspace carries an attacker's API key and tricks the agent into sending data to the Anthropic API under that key. The API address is on the egress allowlist anyway, so ordinary network rules can't stop it.

### Observability: isolation also blinds your own security tools

After Cowork launched, enterprise security teams asked why their endpoint detection and response (EDR) software couldn't see inside the VM. The isolation that keeps Claude in also keeps the host's security tools out. To EDR, Cowork is one opaque hypervisor process.

Every new layer of isolation means redesigning observability. The stronger the isolation, the more the agent has to report on itself.

## 6. Which topology for which job

The sections above explain where topologies come from. This one gives a verdict. Use the four questions in figure 8 to pick a topology, then check the table for what it buys and what it costs.

![Four questions pick the topology](/figures/head-in-the-cloud/fig-8-decide.en.svg)

| Job | Topology | You get | You pay |
|---|---|---|---|
| A developer at their own machine, working on a local repo | 1 Fully local | No setup, no added latency, every local resource at hand | Work stops when the device does; safety depends on per-step approval |
| Let the agent run on its own without per-step approval | 3 Local runtime + sandbox | High autonomy, keys outside the box, the agent survives execution failures | A boundary and a file mount to maintain |
| A one-off experiment with no credentials in the environment | 2 Whole agent in a box | The simplest setup, disposable | Not for long-term use; any credential inside can leak |
| Clonable repo, several long tasks in parallel, output is a pull request | 4 Cloud-hosted | Parallelism; work continues with the laptop closed | No access to local resources; the vendor holds the data and the bill |
| Work that needs the user's logged-in sessions, such as admin consoles or sites behind a login | 5 Cloud runtime + local exec | Access to resources that can't be copied | The local device must be online; permissions must be enforced locally |
| A personal assistant you message from a chat app, working on your own files and accounts | 6 Remote access + home runtime | Always on, local resources, no new app to install | A machine to maintain; every chat message becomes agent input |
| An assistant for employees | 7 Company chat app + cloud | Identity, org chart and permissions come ready-made | Capabilities limited by the chat platform's APIs |
| Heavily regulated industries such as finance, government, healthcare | On-premises, everything inside the network | Compliance | Weaker models, higher operating cost |
| A general desktop assistant for non-developers | 3 + 8 | Safety plus local resources; each tool gets the right execution environment | The most complex system; observability must be redesigned |
| The model you want isn't reachable where you are | Not the overseas-server setup; keep the runtime and swap the model | Compliant, stable, no ban risk | Accept a different model's capabilities |

The table comes down to three sentences.

**Resources decide where execution runs.** If they can be copied, go to the cloud. If not, execution stays where the resources are.

**Uptime decides where the runtime runs.** If tasks outlive the device, move the runtime somewhere always on. Otherwise local is simplest.

**Trust boundaries decide where permissions are enforced.** When runtime and execution sit in different trust domains, enforce on the execution side, and keep credentials on the side that doesn't run untrusted code.

## 7. Conclusion

**Topologies won't converge, but the interfaces between the parts will.** The forces are here to stay: some resources can be copied and some can't, some devices stay on and some don't, model output will never be trusted, and networks and regulations differ by region. So all of these topologies will keep existing. What converges is the three interfaces. The runtime-to-model interface is already close to standard; Chinese models offering Anthropic-compatible endpoints are proof. The runtime-to-execution interface is being filled in by MCP and the sandbox APIs. The access-to-runtime interface, a session protocol with resume, multi-device sync and asynchronous approval, is the least standardized of the three.

**The runtime will stop caring where it runs.** A runtime that is stateless and persists all of its state can run on a laptop, a Mac mini, an overseas server or a cloud cluster without code changes.

**Execution environments will become attachable resources, not fixed properties of a session.** A session can attach several, swap one mid-task, and treat an execution failure as an ordinary event.

**Advice for anyone building agent infrastructure:** build the parts as separate processes that talk through explicit interfaces from day one, even while they all run on one machine. When the day comes to move one of them, the boundary is already there. Cowork could move its agent loop out of the VM, and users in China could move their runtime overseas, because that boundary was already there.

## References

- Li Ao, "Presented to the Monk Weiyan of Mount Yao" (Tang dynasty): "云在青天水在瓶", clouds in the blue sky, water in the vase.
- Anthropic, [How we contain Claude across products](https://www.anthropic.com/engineering/how-we-contain-claude) (May 2026)
- Anthropic, [Making Claude Code more secure and autonomous with sandboxing](https://www.anthropic.com/engineering/claude-code-sandboxing)
- The Decoder, [Anthropic bans companies majority-controlled by China, Russia, Iran, and North Korea from Claude](https://the-decoder.com/anthropic-bans-companies-majority-controlled-by-china-russia-iran-and-north-korea-from-claude/) (September 2025)
- Investing.com, [Anthropic targets loopholes used by Chinese firms to access Claude, FT reports](https://www.investing.com/news/stock-market-news/anthropic-targets-loopholes-used-by-chinese-firms-to-access-claude-ft-reports-4774998) (July 2026)
- [OpenClaw documentation](https://docs.openclaw.ai/)
- Manus, [Introducing Manus Browser Operator](https://manus.im/blog/manus-browser-operator) (November 2025)
- Mindgard, [Manus Rubra: the browser extension with its hand in everything](https://mindgard.ai/blog/manus-rubra-full-browser-remote-control)
- Help Net Security, [Anthropic's Remote Control feature brings Claude Code to mobile devices](https://www.helpnetsecurity.com/2026/02/25/anthropic-remote-control-claude-code-feature/) (February 2026)
- HackerNoon, [Claude Code launches Teleport workflow](https://hackernoon.com/claude-code-launches-teleport-workflow-start-anywhere-continue-everywhere)
- Tencent Cloud, [OpenClaw cloud deployment](https://cloud.tencent.com/act/pro/openclaw); Alibaba Cloud Developer Community, [one-click OpenClaw deployment](https://developer.aliyun.com/article/1720712)
- Tencent Cloud Developer Community, [official WeChat plugin for OpenClaw](https://cloud.tencent.com/developer/article/2648517)
