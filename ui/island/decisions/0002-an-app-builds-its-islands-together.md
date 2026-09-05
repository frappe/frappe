# An app builds its islands together

One Vite build takes all of an app's islands as its entries. Rollup lifts what two entries share into a chunk both import. It writes each entry as `<name>.island.<hash>.js` beside a `chunks/` directory.

## Decision

`buildIslands` takes the whole entry list and runs one build.

An island bundles its own Vue and its own frappe-ui ([0001](0001-an-app-bundles-its-own-island.md)). Within one app that cost is paid once. Two islands built together share one chunk for Vue, one for frappe-ui and one for every helper they both import. The app's second island costs only what it alone adds.

The browser loads an entry and the chunks that entry statically imports. `budget` weighs that closure plus the app's stylesheet. That is the bytes a reader waits for to see one island, not the bytes on disk. A dynamic import is work the island deferred, so the build reports it and does not charge it.

Chunks need no registration. The entry imports them by relative path, and `base` points at the app's island directory, so the browser resolves them from the entry it already has.

## Rejected: one build per entry

Each entry gets its own Vite build, its own output directory and its own stylesheet.

Nothing is shared, so every island carries a full copy of Vue, frappe-ui and the app's helpers. The Tailwind scan needs a throwaway build ([0003](0003-tailwind-scans-the-module-list-not-a-glob.md)), and this multiplies that build by the number of entries.

The one thing it buys is an output directory per entry, which makes `emptyOutDir` safe. One directory per app is as safe, because the app's island build is the only writer under it.

## Rejected: a hand-written `manualChunks`

Name the shared packages and force them into a vendor chunk.

Rollup already knows which modules two entries reach. A hand-written list is a second description of that, and it goes stale the first time an entry stops importing a package. It also fixes the split at package granularity, where Rollup splits at module granularity.
