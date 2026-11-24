# Skills and MCP

Skills and MCP are both ways to bring content from outside the engine to the model: a skill is a set of instructions written for the model, installed per role in the skills directory; an MCP (Model Context Protocol) server is a tool service someone else has built, which each user registers in their own settings. Both join that user's tool set as tool providers (`kit.Provider`). For the tool set, the life of one call and deferred loading, see [Tools](/engine/tools); this page covers each one's format, how it is assembled, and its limits.

::: info Full page in Chinese
This page is being translated. The complete version, with every detail and code reference, is [in Chinese](/zh/engine/skills-mcp).
:::

The full page covers:

- Why it is designed this way
- What a skill is
- Discovery and loading
- How a skill enters the context
- Configuring MCP servers
- The MCP client
- Failure, status and cleanup
- Permissions and the sandbox
- The workspace layer
- Limits and known issues
