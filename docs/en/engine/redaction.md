# Redaction

Redaction replaces sensitive values with placeholders before a request is sent to the model, and puts the original values back after the model's answer returns. The model never sees values such as phone numbers and keys; what users and tools see is unaffected. `pkg/redact` only replaces text; it is called by the model calls in a run (`run/model.go`) and by memory extraction (`extract`).

The replacement works both ways: what goes out is `<PHONE:a1b2c3d4>`, the model's answer uses the same placeholder, and once it is restored the interface and tools get the real number. When the model needs to act on the value, the arguments of its tool calls are restored too, so the task is unaffected. For where redaction sits in the overall security design, see [Security overview](/engine/security).

::: info Full page in Chinese
This page is being translated. The complete version, with every detail and code reference, is [in Chinese](/zh/engine/redaction).
:::

The full page covers:

- Why it is designed this way
- What is recognised
- HMAC placeholders
- When and where values are replaced
- The switch
- Limits and known issues
