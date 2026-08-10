# Experimental

Work in progress. Nothing here is production ready: the APIs, the file layout and
the backing DocTypes all still move without notice, and none of it is covered by
the compatibility promise the rest of `@framework/ui` makes.

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
