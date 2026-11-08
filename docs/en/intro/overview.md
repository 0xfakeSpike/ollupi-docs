# Overview

Ollupi is two projects: a Go agent engine, and a macOS desktop app built on it.

| | ollupi | ollupi-desktop |
|---|---|---|
| What | A Go library, an agent runtime | An Electron app with a Go backend, `ollupid` |
| For | Cloud providers building personal agent services at scale | People using an agent on their own Mac |
| Shape | One process hosts every user and session of one shard | One local user; the backend runs as a sidecar hosted by the app |
| Interface | JSON-RPC 2.0 over WebSocket | The desktop interface and a Feishu bot |
| Repository | [0xfakeSpike/ollupi](https://github.com/0xfakeSpike/ollupi) | [0xfakeSpike/ollupi-desktop](https://github.com/0xfakeSpike/ollupi-desktop) |

Why the engine is built this way is on [Why Ollupi](/intro/why).

![Ollupi architecture](/images/architecture.svg)

## How the two relate

The desktop app sits downstream of the engine. Its `sidecar/go.mod` depends on a released engine version, and the app only presents and assembles:

- The engine provides sessions, scheduling, persistence, tools, permissions, the sandbox, memory, scheduled tasks, search and the protocol.
- The sidecar assembles the engine and adds what only a local machine has: the configuration file, the built-in browser tools, the Feishu bot.
- The interface talks to the backend only through the protocol, with types generated from the engine's `protocol.schema.json`.

The rule is that logic lives in the layer that owns it. What the engine can do, the app does not do again.

## Where to start

| You want to | Start here |
|---|---|
| Use the desktop app | [Desktop app quickstart](/app/install) |
| Embed the engine in your service | [Embed the engine](/integrate/embed), [Gateway protocol](/integrate/protocol) |
| Understand how it works | [Core concepts](/intro/concepts), [Architecture](/engine/architecture), [Execution model](/engine/execution) |
| See performance data | [Benchmarks](/benchmarks/) |
| Know why it is designed this way | [Design decisions](/reference/decisions), [History](/reference/history), [Articles](/articles/) |
| Know what comes next | [Roadmap](/roadmap) |

## Languages

The site is written in English and Chinese. Pages are being translated into English one by one; an English page that is not finished yet says so at the top and links to the complete Chinese version.
