# A page island reports its title and its actions

A page island fills a page. It still needs a page header: a title, and the actions that belong to what it shows. The island knows both, because it loaded the document. The header belongs to the host, which already has one for every other page.

## Decision

A page island ships no header. It reports what a header would say:

- `title`, a `string` or `null`.
- `actions`, an `Action[]`. An `Action` is `{ label, icon? }` plus either an `onClick` or an `href`.

An `onClick` runs in the island. An `href` is a URL, absolute or site-relative, to a page outside the host app. The action reports where it goes. The host decides what a link out of the app does. A host opens it in a new tab, and may mark the action as one that leaves the app, in its own idiom.

An island that fills less than a page, such as a widget in a workspace, reports neither. A host that has no header binds neither. The `Action` fields are what one island needs, and both hosts show them as a menu row. A new field is a change both hosts make together.

Each host sets its own chrome from the report. Desk sets the page title and fills the page menu. A frappe-ui app fills its `LayoutHeader`. The island does not know which host it is in, and each host's header stays native.

Both are plain events. A Vue host binds them with `@title` and `@actions`. A desk caller passes `onTitle` and `onActions`. See [0009](0009-an-island-takes-vues-props-object.md).

## Rejected: `update:` events, bound with `v-model`

`update:title` and `update:actions`, so that a Vue host writes `v-model:title`.

`v-model:actions` is `:actions` plus `@update:actions`, and the island declares neither prop. The binding passes a value into a component that ignores it, and it reads as state the host and the island share. Nothing is shared. The island reports and the host stores, which is what a plain event says.

The sugar also cost `<Island>` a filter. It had to strip every `update:`-shaped attribute out of the island's props object. Otherwise the value a host bound came back down as a stray attribute, and each report echoed through `update`. A plain event passes nothing down, so the filter went with it.

## Rejected: the island draws its own header

It knows the title first, so it could render the header.

Every host already has a header. The island's header landed under desk's. The dashboard page had to hide desk's page head to make room. That cost it the breadcrumb trail, the page menu and the title slot. All three then reached the island as context it had to render again. A second host would repeat the whole negotiation.

## Rejected: the island opens the other app itself

An action that leaves for another app is an `onClick` that calls `window.open`.

Then the island chose the new tab and a label that named the destination. Both belong to the host. A desk menu row and an in-app header read differently, and only the host knows which it shows. The SPA host had to tell the island not to leave, through a provider flag. That is the island holding a decision it cannot make. An `href` states the destination and stops.

## Rejected: a `header: boolean` prop

Let the caller ask for the header, or not.

A toggle over a design that was wrong on both settings. The island still carries header code, every host still decides, and the two paths drift.
