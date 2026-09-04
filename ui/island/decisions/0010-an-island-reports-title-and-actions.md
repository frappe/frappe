# An island reports its title and its actions

An island that fills a page still needs a page header: a title, and the actions
that belong to what it shows. The island knows both — it loaded the document. The
header belongs to the host, which already draws one for every other page.

## Decision

An island ships no header. It emits what a header would say:

- `title` — a `string` or `null`.
- `actions` — an `Action[]`, `Action` being `{ label, icon? }` plus either an
  `onClick` or an `href`.

An `onClick` runs in the island. An `href` is a URL — absolute or site-relative — to a
page outside the host app: the action reports where it goes, and the host decides how a
link into another app behaves. A host opens it in a new tab, and may mark the action as
leaving the app, in its own idiom.

Each host draws its own chrome from them. Desk sets the page title and fills the
page menu; a frappe-ui app fills its `LayoutHeader`. Nothing in the island knows
which host it is in, and each host's header stays native — desk's menu is a desk
menu, and it is where a desk reader looks for it.

Both are plain events. A Vue host binds them with `@title` and `@actions`, and a
desk caller passes `onTitle` and `onActions`. See
[0009](0009-an-island-takes-vues-props-object.md).

## Rejected: `update:` events, bound with `v-model`

`update:title` and `update:actions`, so that a Vue host writes `v-model:title`.

`v-model:actions` is `:actions` plus `@update:actions`, and the island declares
neither prop. The binding passes a value into a component that ignores it, and it
reads as state the host and the island share. Nothing is shared. The island
reports and the host stores, which is what a plain event says.

The sugar also cost `<Island>` a filter. It had to strip every `update:`-shaped
attr out of the island's props object, or the value a host bound came back down
as a stray attribute and echoed each report through `update`. A plain event
passes nothing down, so the filter went with it.

## Rejected: the island draws its own header

It knows the title first, so it could paint it.

Every host already has one. The island's header landed under desk's, and the
dashboard page had to hide desk's page head to make room — which cost it the
breadcrumb trail, the page menu and the title slot, all of which then reached the
island as context it had to redraw. A second host would repeat the whole
negotiation.

## Rejected: the island opens the other app itself

An action that leaves for another app is an `onClick` that calls `window.open`.

Then the island chose the new tab and a label naming the destination, both of which
belong to the host: a desk menu row and an in-app header read differently, and only the
host knows which it draws. The SPA host had to un-know it through a provider flag,
telling the island not to leave, which is the island holding a decision it cannot make.
An `href` states the destination and stops.

## Rejected: a `header: boolean` prop

Let the caller ask for the header, or not.

A toggle over a design that was wrong on both settings. The island still carries
header code, every host still decides, and the two paths drift.

## Rejected: one `page` snapshot event

`emit("page", { title, actions })`, one event for the lot.

A bag again, and its name says nothing about when it fires. Two `update:` events
say what changed, and each binds to the one piece of host state it owns.

## Rejected: state on the mount handle

`island.title`, read by the host.

The host cannot track it. The island runs its own copy of Vue behind a shadow
root, so nothing the host holds is reactive against it, and the host would need a
change event to know when to read — which is this decision, with a second path
into it.
