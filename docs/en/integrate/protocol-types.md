# Protocol data types

The reference for the named types (`$defs`) in the gateway contract `protocol.schema.json`: what each field is, when it appears and which values it takes. Methods, notifications, server requests, error codes and enum values are on the [gateway protocol](/integrate/protocol) page.

::: info Full page in Chinese
This page is being translated. The complete version, with every field and real JSON examples, is [in Chinese](/zh/integrate/protocol-types).
:::

The full page covers:

- Conventions: optional fields, times, IDs, snake_case types
- Sessions, turns and items: `ThreadRow`, `TurnRow`, `Usage`, `ItemRow` by item type, `Await`, `Attachment`, `ContextStats`, `ToolResult`, providers
- Approvals and questions: `ApprovalRequestParams`, `Approval`, `Prepared`, `FileChange`, question and answer types
- Built-in tools' arguments and outputs
- Catalogue types: `Model`, `ToolDescriptor`, `ServerStatus`, `WorkspaceRow`, `EnvironmentRow`, `CronJobView`, memory, `SearchResult`, permission settings, `SettingsRow`
