# Experimental

Work in progress. Nothing here is production ready: the APIs, the file layout and
the backing DocTypes all still move without notice. Neither is anything else —
this package is version `0.0.0` and states no compatibility policy anywhere, so
there is no promise here to be excluded from.

The one exception is the Record page customization API, whose intent is written
down because scripts stored in site databases outlive every upgrade:
[`RecordPage/COMPATIBILITY.md`](./RecordPage/COMPATIBILITY.md).

The package exposes one entry, so a call site is honest about what it depends on:

```ts
import { useNavigation } from "@framework/ui/experimental";
```

The barrel reaches every `.vue` component in here. A module that wants a pure
helper and not the form runtime should still import the leaf directly, the way
`src/components` does:

```ts
import { displayValue } from "@framework/ui/experimental/PanelLayout/displayValue";
```

A folder graduates by moving to `src/components/` (or `src/composables/`) once its
API has settled and its server side has landed on `develop`.
