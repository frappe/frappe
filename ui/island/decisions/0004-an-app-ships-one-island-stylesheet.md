# An app ships one island stylesheet

The build extracts one stylesheet for all of an app's islands. Every entry
registers it under its own `<name>.island.css` key, so the loader hands each
island the same URL and the mount contract adopts one `CSSStyleSheet` object into
every shadow root.

## Decision

`cssCodeSplit: false`, one Tailwind config per app, one sheet.

The sheet is complete on its own. A shadow root inherits no document styles, so
the sheet carries `@tailwind base` — preflight and the theme tokens — as well as
the components and utilities layers. The preset rewrites `:root`, `html` and
`body` to `:host`, because nothing inside a shadow root matches those.

The browser fetches and parses it once per page whatever the island count, and
`adoptedStyleSheets` shares the parsed object rather than a copy. An island
therefore pays for the sheet once, not once per mount.

The cost is that an island carries rules for classes its siblings use. Utilities
compress well and the whole app's island CSS is smaller than the second copy of
preflight that per-island sheets would ship.

## Rejected: a stylesheet per island

`cssCodeSplit: true` and a Tailwind config per entry.

Preflight and the theme tokens are the floor of any island sheet, and they repeat
in every one. Splitting also puts the CSS of a shared chunk in its own file, so
the loader would have to carry a list of sheets per island instead of a URL, and
the mount contract would have to keep their order stable across islands.

## Rejected: a framework stylesheet every island inherits

One sheet built by framework and adopted before the island's own, so islands
share preflight and frappe-ui's utilities.

An island's classes come from the modules it is built from
([0003](0003-tailwind-scans-the-module-list-not-a-glob.md)). A sheet built
somewhere else is scanned from a different tree, and a class that tree does not
have gets no rule on any island, everywhere, silently. It also puts framework
back in the business of building the app's dependencies
([0001](0001-an-app-bundles-its-own-island.md)).
