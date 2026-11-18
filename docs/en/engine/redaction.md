# Redaction

Redaction replaces sensitive values with placeholders before a request goes to the model, and restores them when the model's answer comes back. The model never sees phone numbers, keys and the like; what users and tools see is unchanged, and the conversation log keeps the real values. Placeholders are HMACs under a key each user keeps, so the same value always gets the same placeholder.

::: info Full page in Chinese
This page is being translated. The complete version, with every detail and code reference, is [in Chinese](/zh/engine/redaction).
:::

The full page covers:

- What is recognised
- HMAC placeholders
- When and where values are replaced
- Switching it on
- Limits
