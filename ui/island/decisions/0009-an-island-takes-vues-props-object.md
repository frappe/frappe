# An island takes Vue's props object

An island is a Vue component behind a shadow root. A host passes it data and listeners. The host API says how the two travel together.

## Decision

They travel as Vue's props object: data keys and `on*` listener keys in one flat object, exactly what `h(Component, props)` takes.

```js
frappe.ui.mount_island("insights.dashboard", el, {
	dashboard: "sales",
	onNavigate: (route) => frappe.set_route(route),
	onTitle: (title) => frappe.utils.set_title(title),
});
```

`mountVueIsland` hands that object to `h` untouched. `update` merges into it, which is what a re-render does. `<Island>` takes the same object as attributes. Everything but `name` and `context` passes through verbatim, so `@title` and `@navigate` work on it as they do on any component.

The shape has no translation layer, so it has no rules to learn. A caller who knows Vue knows this API. A component author reads the props their component declares.

## Rejected: a structured bag, `{ props, on, model }`

The first shape. `mount.js` turned `on.navigate` into `onNavigate`. `Island.vue` turned `@navigate` into `on.navigate`. Desk's caller wrote a third form. Three translations of one idea, and each one a place where a name can be spelled right and still not arrive. It was also a syntax of our own that nobody knows on arrival.

## Rejected: camelCase listener names, `onUpdateTitle`

It reads better, and it never fires. Vue camelizes a hyphen in an event name, not a colon. `update:title` resolves as the literal key `"onUpdate:title"` and nothing else. A name Vue cannot resolve fails without a report, which is the worst way for a listener to be wrong.

The island API has no colon in an event name any more. [0010](0010-a-page-island-reports-title-and-actions.md) dropped the two it had. The rule still governs any component a host mounts, which is why the object goes to `h` untouched.
