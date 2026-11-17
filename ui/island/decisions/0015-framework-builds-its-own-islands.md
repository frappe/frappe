# Framework builds its own islands

Desk draws its charts with an island, `frappe.chart`. A page island is additive: a page that is unbuilt shows an unbuilt state and nothing else breaks. A chart island is not. Every report, dashboard and form graph draws through it, so an unbuilt chart is a broken desk.

## Decision

Framework builds its own islands like any app builds its own ([0001](0001-an-app-bundles-its-own-island.md), [0002](0002-an-app-builds-its-islands-together.md)): one build, all entries, output in `sites/assets/frappe/dist/island/`. It roots the build at `island-toolchain/` like the page-island build ([0013](0013-framework-builds-page-islands.md)), and the two share the install step.

The entries are a table in `ui/vite/island/framework.js`, not a scan. They are a fixed part of framework, and a missing entry fails the build instead of dropping out of it.

`bench build` runs it straight after esbuild, and a failure fails the command. The page-island build still runs from `after_app_build` and only warns. `bench watch` starts both watchers.

This amends 0013, which had framework run one island build, from the hook. Each build ships one stylesheet ([0004](0004-an-app-ships-one-island-stylesheet.md)), so framework now ships two: one for its own islands, one for page islands.

The cost is a second build pass and a second copy of Vue and frappe-ui on disk. A page that shows a chart and a page island loads both.

## Rejected: chart entries in the page-island build

Add `frappe.chart` to the entries of the build that already runs on every bench, so it shares that build's Vue and frappe-ui chunks.

One Rollup build fails as a whole. A syntax error in any app's page island would take desk's charts down with it, so the build could not fail `bench build` without making every app's page fatal too. The build also owns `dist/page-island/` and its keys, which would then mix islands with two failure rules in one directory.

## Rejected: register the build first in `after_app_build`

An exception there also aborts `bench build`. But the hook is how an app reacts to another app's build, and this is framework's own asset build, with its own failure rule. `build()` calls it next to esbuild, where a reader looks for what `bench build` builds.
