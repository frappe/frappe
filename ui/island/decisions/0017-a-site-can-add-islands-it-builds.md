# A site can add islands it builds

[0014](0014-assets-json-is-the-island-registry.md) made assets.json the registry. assets.json lists what `bench build` built. Some islands are built later, on the site, from records a user edits. A Studio app is one: its build lands in the site's files when someone publishes it, and assets.json never names it.

## Decision

An app adds those islands with an `island_assets` hook. The hook is a method that returns entries in assets.json's own shape, `<name>.island.js` and `<name>.island.css` mapped to URLs.

```python
island_assets = ["someapp.islands.get_island_assets"]
```

`get_island_assets_json()` is assets.json with every hook's entries over it. Boot carries it as `assets_json`, and `get_island_assets` resolves against it, so neither host changes. `get_ui_islands()` lists the names in both.

The installed-app filter does not apply to a hooked island. assets.json is bench-wide, so the filter keeps another site's islands out. A hook runs on this site only, so what it returns is already this site's.

## Rejected: the app writes its islands into assets.json

The builds would then need the bench's assets folder, and one site's island would appear on every site of the bench. It would also be lost the next time `bench build` writes the file.

## Rejected: boot gets a second registry

A `ui_island_assets` map next to `assets_json`, read by the loader before it reads assets.json.

Two sources for one lookup, and each host has to know both. The hook keeps one map with one shape, and the loader stays as it is.
