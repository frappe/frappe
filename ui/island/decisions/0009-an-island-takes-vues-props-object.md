# An island takes Vue's props object

An island is a Vue component behind a shadow root. What a host passes it is data
and listeners. The host API says how the two travel together.

## Decision

They travel as Vue's render-function props object: data keys and `on*` listener
keys in one flat object, exactly what `h(Component, props)` takes.

```js
frappe.ui.mount_island("insights.dashboard", el, {
	dashboard: "sales",
	onNavigate: (route) => frappe.set_route(route),
	onTitle: (title) => page.set_title(title),
});
```

`mountVueIsland` hands that object to `h` untouched, and `update` merges into it,
which is what a re-render does. `<Island>` is the same object as attributes:
everything but `name` and `context` passes through verbatim, so `@title` and
`@navigate` work on it as they do on any component.

The shape has no translation layer, so it has no rules to learn. A caller who
knows Vue already knows this API, and a component author reads the props their
component declares.

## Rejected: a structured bag, `{ props, on, model }`

The first shape. `on.navigate` became `onNavigate` in `mount.js`, `@navigate`
became `on.navigate` in `Island.vue`, and desk's caller wrote a third form. Three
translations of one idea, each a place a name can be spelled right and still not
arrive, and a syntax of our own that nobody comes knowing.

## Rejected: camelCase listener names, `onUpdateTitle`

It reads better and it never fires. Vue camelizes a hyphen in an event name, not
a colon: `update:title` resolves as the literal key `"onUpdate:title"` and
nothing else. A name Vue cannot resolve fails silently, which is the worst way
for a listener to be wrong.

The island API has no colon in an event name any more —
[0010](0010-an-island-reports-title-and-actions.md) dropped the two it had. The
rule still governs any component a host mounts, which is why the object goes to
`h` untouched.
