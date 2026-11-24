# Design language

The desktop app's visual language is called **stone and moss**: a guide map drawn for your own errands. Each workspace is an area you recognise by its colour at a glance; inside a task the result comes first, and what was done behind it folds into one plain sentence. It avoids the default look of this kind of product: a long run of commands, paths, models and tokens that you have to read through before you know where things stand.

Every component uses only the semantic tokens defined in `packages/ui/src/theme.css`. This page distils those rules; the full guidelines are in ollupi-desktop's `packages/ui/DESIGN.md`, and the product facts (who it is for, the principles) are in `apps/desktop/PRODUCT.md`. The name and the mark are on [Brand](/desktop/brand).

::: info Full page in Chinese
This page is being translated. The complete version, with every detail and code reference, is [in Chinese](/zh/desktop/design).
:::

The full page covers:

- Who it is for, and the starting point: AI makes things simpler
- Information hierarchy: what needs you, the result, the process, the meta information
- One signal, everything else quiet: ochre means only "needs you"; actions are moss
- The window: a stone ground and a paper sheet
- Themes: stone and moss, and dusk, each in light and dark
- Tokens: colours (light and dark), type sizes, radii, shadows, motion
- Component notes: results first, the approval card, approval policies in plain words, side panels that lead with the conclusion, the little wolf only in empty states
- Copy
- Checks
