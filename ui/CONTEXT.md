# List View (shared @framework/ui)

The domain of the reusable doctype list-view experience being extracted from CRM
into `@framework/ui`: the toolbar controls a user manipulates to shape a list
(sort, filter, columns, quick filters) and the composite that assembles them.

## Language

**List View Controls**:
The toolbar pieces a user manipulates to shape a doctype list — **SortBy**,
**Filter**, **Column Settings**, **Quick Filter**, and **Group By**. Each is an independent,
controlled component that owns one slice of view state.
_Avoid_: "view controls" (CRM's name; it carries the CRM-specific Views concept).

**Sort**:
A single ordering rule: a `fieldname` plus a `direction` (`asc`/`desc`). A list's
ordering is an ordered list of Sorts.
_Avoid_: order, ordering rule.

**order_by**:
The Frappe wire form of an ordering — a comma-joined string like
`"modified desc, name asc"`. The serialized form of a list of **Sort**s.
_Avoid_: sort string.

**Filter**:
A precise, fieldtype-aware condition on a doctype field, set through the Filter
control's popover. The full/advanced way to narrow a list.

**Quick Filter**:
A pre-chosen field surfaced inline in the toolbar for one-tap narrowing. A
convenience projection over **Filter**s — a Quick Filter and its matching
**Filter** describe the same underlying condition and stay in sync.
_Avoid_: inline filter.

**Group By**:
The fields a list is grouped by, in order, plus its **Aggregate**s. Grouped, the list
shows one summary row per distinct combination of those fields' values instead of its
records — desk's report view group by. `null` means ungrouped.
_Avoid_: group by view (CRM's name for a list whose records sit under group headings).

**Aggregate**:
A summary column of a grouped list: a function (`count`, `sum`, `avg`, `min`, `max`)
and, for all but `count`, the field it runs on.
_Avoid_: total, rollup.

**Column**:
One shown column in the list: a `fieldname`, a (user-overridable) `label`, and an
optional CSS `width` (`"11rem"`, `"120px"`). The Column Settings control's state is
an ordered list of Columns — presence means shown, array order is display order, and
`width` is the slice a column resize co-writes. A column's `align`/`type`/`options`
are not stored here; they are derived from **Meta** at render/serialize time.
_Avoid_: field, column setting (the control, not the datum), key (CRM's `key` ≙ `fieldname`).

**Field Options**:
The list of a doctype's fields a control offers (e.g. SortBy's sortable fields).
Derived client-side from doctype **Meta**, not from a CRM endpoint.
_Avoid_: sort_options, filterable fields (CRM endpoint names).

**Meta**:
A doctype's field definitions, fetched via the shared `useDoctypeMeta`
composable. The single source from which Field Options are derived.

**Controlled component**:
A control that owns only its own state slice via `v-model` plus a `doctype`,
emits changes, and never touches a data-fetching resource or persistence. The
host wires fetching, persistence, and cross-control sync.
_Avoid_: connected component, smart component.

**View Snapshot**:
The serialized, persist-able capture of a List View's state — its **Filter**s,
**Sort**s, **Column**s, surfaced **Quick Filter** fields, and **Group By**. The unit a host's
persistence layer is handed. It carries **no identity, ownership, or named-View
concept** — whether this is a "standard", public, pinned, or named **View**, and
who owns it, belongs entirely to the consuming app. The library tops out here and
never owns a saved **View** entity; the host wires _when_ and _where_ to save it
([ADR-0007](docs/adr/0007-persistence-deferred-to-host-library-tops-out-at-view-snapshot.md)).
_Avoid_: view, saved view, view settings (all carry CRM's Views concept).

**Composite List View**:
The shared module (`ListView/`) that assembles the controls into a full list view
behind a `useListView` state composable. The home of the integration "shell" story
used to chase pixel parity with CRM. Kept for now; the desk list page composes the
**List module** and the controls directly instead.

**Shell story**:
The combined story in the Composite List View module that mounts the controls
together against a real doctype to verify pixel parity with CRM's list view.
Distinct from each control's own isolated story.

**List module**:
The experimental module (`experimental/List/`, subpath `./experimental/List`) that holds
the table (`List`), the footer (`ListFooter`) and the selection bar (`ListBulkBar`) a
doctype list page composes beside the controls. Experimental: its API can change with
no deprecation window until the desk list page has settled it. The
host lays them out, fetches the rows, and binds the same **Column**s and **Sort**s the
controls edit; the table itself fetches and stores nothing.

## Example dialogue

— "When I change the SortBy chip, does it write `order_by` back to the resource?"
— "No. SortBy is a **controlled component** — its `v-model` is a list of
**Sort**s. It just emits the new array; the host serializes it to **order_by**
and refetches."
— "And where do the sortable fields come from — the `sort_options` endpoint?"
— "No CRM endpoint. **Field Options** are derived from the doctype's **Meta**."
— "If I set a **Quick Filter** for Status, does the Status **Filter** update too?"
— "Yes — a Quick Filter is a projection over Filters; they describe the same
condition and stay in sync once the shared composable lands."

# Email Accounts (shared @framework/ui)

The settings panel for a site's mailboxes (`EmailAccounts/`), shared so any app can host it.

## Language

**Email Account**:
A mailbox the site sends from or receives into, as Frappe's Email Account doctype stores it.
_Avoid_: email config, email setup.

**One-click sign-in**:
Connecting a mailbox by signing in to its provider through Frappe Cloud
(`email_oauth.initiate_mailbox_connect`), with no password or OAuth app to set up. Only on
Frappe Cloud v2 sites, which the host tells the panel from its boot (`isV2Site`).
_Avoid_: relay connect, OAuth connect (OAuth also covers an account's own app).

**Auth kind**:
How an account authenticates: **Password**, **Frappe Mail** (API key), **OAuth** (one-click
sign-in, whose Connected App's token URI starts with `frappe-cloud-relay:`), or
**OAuth: custom app** (a Connected App the site set up itself).

**Account status**:
An account's state, shown in the list's status badge. **Needs reconnect**: an OAuth account
with no token left (Frappe drops the token when the provider rejects its refresh).
Anything else is **Active**, and its badge says which way it works: **Incoming & outgoing**,
**Incoming only**, **Outgoing only**, or **Disabled** when neither.

**Reconnect**:
Running one-click sign-in again for an existing **OAuth** account, from its edit screen or
its Desk form, which moves it to a fresh token without creating a new account. A signed-out
**OAuth: custom app** account whose provider the site offers one-click sign-in for is
reconnected the same way, which moves it to one-click sign-in and leaves its own app in place.
Anywhere else, it is authorized again in Desk.
_Avoid_: re-authorize (Desk's name for a custom app's flow).

**Default incoming / Default outgoing**:
The one account replies come into and the one account mail is sent from, picked once for
the whole list rather than on each account.
