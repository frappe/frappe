# An island reports its title and its actions

An island that fills a page still needs a page header: a title, and the actions
that belong to what it shows. The island knows both — it loaded the document. The
header belongs to the host, which already draws one for every other page.

## Decision

An island ships no header. It emits what a header would say, as child-owned
state:

- `update:title` — a `string` or `null`.
- `update:actions` — an `Action[]`, `Action` being `{ label, icon?, onClick }`.

Each host draws its own chrome from them. Desk sets the page title and fills the
page menu; a frappe-ui app fills its `LayoutHeader`. Nothing in the island knows
which host it is in, and each host's header stays native — desk's menu is a desk
menu, and it is where a desk reader looks for it.

The two are `update:` events, so a Vue host binds them with `v-model:title` and
`v-model:actions` and a desk caller passes `"onUpdate:title"`. See
[0009](0009-an-island-takes-vues-props-object.md).

## Rejected: the island draws its own header

It knows the title first, so it could paint it.

Every host already has one. The island's header landed under desk's, and the
dashboard page had to hide desk's page head to make room — which cost it the
breadcrumb trail, the page menu and the title slot, all of which then reached the
island as context it had to redraw. A second host would repeat the whole
negotiation.

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
