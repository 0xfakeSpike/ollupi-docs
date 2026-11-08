# Build and release

The desktop app is released on GitHub Releases for Apple silicon only; each release has a dmg, a zip and `latest-mac.yml`. The dmg is for first installs, the zip for automatic updates. The app is ad hoc signed and not notarized by Apple, so the updater is written in-house rather than using Squirrel.Mac.

::: info Full page in Chinese
This page is being translated. The complete version, with every detail and code reference, is [in Chinese](/zh/desktop/release).
:::

The full page covers:

- Build flow
- Only arm64
- Release artifacts
- Automatic updates
- Version numbers
- Signing and notarization
