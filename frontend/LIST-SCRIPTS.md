# Moving a v1 list script to a v2 `list.js`

A desk v1 list script is a `<doctype>_list.js` file that sets `frappe.listview_settings["<DocType>"]`. Desk v2 does not run it. On desk v2, a list script is a `list.js` file beside the doctype, in `<doctype>/frontend/list.js`. This guide turns a v1 list script into that file, one v1 key or call at a time.

The reference for every `page` member in this guide is the section "The list page: `list.js`" in [`SCRIPTING.md`](SCRIPTING.md). The types are in `frontend/src/listPage/types.ts`.

## How to read this guide

Find the v1 key or call in the list below. Its section gives one of two answers:

- **The v2 shape**, with a short v1 "before" and a v2 "after". Most pairs come from frappe's own ports.
- **No v2 shape (gap)**, with what to do instead. The [Gaps](#gaps) list at the end collects them.

Keys: [`get_indicator`](#get_indicator), [`add_fields`](#add_fields), [`filters`, `order_by`](#filters), [`hide_name_column`](#hide_name_column), [`disable_comment_count`](#disable_comment_count), [`has_indicator_for_draft`, `has_indicator_for_cancelled`](#has_indicator_for_draft), [`onload`](#onload), [`refresh`](#refresh), [`before_render`](#before_render), [`button`](#button), [`formatters`](#formatters), [`prepare_data`](#prepare_data), [`primary_action`](#primary_action), [`get_form_link`](#get_form_link), [`set_title`](#set_title), [calendar view](#calendar).

Calls: [`add_action_item`, `add_actions_menu_item`](#add_action_item), [`call_for_selected_items`](#call_for_selected_items), [`add_inner_button`, `add_menu_item`](#add_inner_button), [`frappe.call`](#frappe_call), [`listview.refresh()`](#listview_refresh), [`frappe.confirm`, `frappe.prompt`, `frappe.ui.Dialog`](#dialogs), [`frappe.show_alert`, `frappe.msgprint`](#show_alert), [`frappe.datetime`](#frappe_datetime), [`frappe.set_route`](#set_route), [`frappe.realtime`](#realtime), [page indicators and retention messages](#set_indicator).

## How the v2 file and the v1 file live side by side

Keep the v1 `_list.js` file. Desk v1 still runs it, and desk v2 never reads it. The v2 `list.js` is a new file. Change both files when you change the behavior, until desk v1 is gone.

A site can also add a list script without an app. Make a `Client Script` row with **Apply To** (`view`) set to `List Page` and **DocType** set to the doctype. Its text is the same as a `list.js`. Desk v1 never runs it. An app that changes another app's list uses `<app>/<module>/custom/<scrubbed>/list.js`.

## What changes in every script

These rules apply to every section below:

- **One module, one object.** A `list.js` is an ES module. Its default export is an object of handlers. A key that is not a function is ignored.
- **Draw in `onRefresh(page)`.** The list page runs it before the first paint, on a return visit, and on `page.refresh()`. A filter, a sort or Load More change only `page.rows`. They do not run `onRefresh`.
- **`listview` becomes `page`.** Every handler and every `run` gets `page` first.
- **Imports.** A script imports by bare name from `vue`, `vue-router`, `frappe-ui`, `@framework/ui` and `frappe/i18n`. There is no global `frappe` object. Get `__` from `frappe/i18n`.
- **No server call on a cold load.** A cold list load must make no extra server call. A v1 `onload` that reads a count or a status from the server before it draws cannot port as it is. A value that boot holds, such as the user's defaults, needs no read. Show the action always, or treat the read as a gap.
- **Data goes in JSON, not JS.** Put default columns, sort and filters in `<doctype>/frontend/views/list.json`.

<a id="get_indicator"></a>
## `get_indicator`

**v2 shape:** a `badge` on the column that holds the value, set with `page.columns.update(fieldname, { badge })`.

A `badge` is a value-to-theme map, or a function `(row) => ({ label, theme, filters })`. The themes are `gray`, `blue`, `green`, `orange` and `red`. Map v1 `amber` and `yellow` to `orange`. v1 `purple` has no theme (gap). The `filters` key takes `[fieldname, operator, value]` triples. With `filters`, a click on the badge adds them to the view's filters, in place of its conditions on the same fields.

A `status` column of type Select or Data already draws a badge, with its color from the doctype's `states`. A `get_indicator` that only colors `status` may need no port.

Before (`auto_repeat_list.js`):

```js
get_indicator: function (doc) {
	var colors = { Active: "green", Disabled: "red", Completed: "blue" };
	return [__(doc.status), colors[doc.status], "status,=," + doc.status];
},
```

After (`auto_repeat/frontend/list.js`):

```js
const THEMES = { Active: "green", Disabled: "red", Completed: "blue" };

page.columns.update("status", {
	badge: (row) =>
		row.status && {
			label: __(row.status),
			theme: THEMES[row.status],
			filters: [["status", "=", row.status]],
		},
});
```

Know these facts:

- A badge function that returns a falsy value keeps the default cell. The `row.status &&` above uses this.
- `label` defaults to the field's own text. `theme` defaults to `gray`.
- The function also runs for an empty value, because it reads the row.
- A function that throws keeps the default cell and logs the error.
- A Check, Rating, Color, Attach, Attach Image or Image column never draws a badge. A v1 indicator built from a Check field (`enabled`, `public`, `published`, `is_standard`, `seen`) cannot sit on its own column. Put a badge function on another column and add the Check field to its `fields` (see the next item), or show the Check column with `switch: true`.
- To show a value with no column of its own, put the badge on another column and rename the column with `label`. `web_form_request` draws its status on `first_used_on`, with `{ label: __("Status"), fields: ["expires_on"], badge: requestStatus }`.

For a static map with no label and no filter, use the map form: `page.columns.update("priority", { badge: { High: "red", Medium: "orange", Low: "gray" } })`.

To put an icon before a value in place of the badge, use `icons`, a value-to-icon map: `{ icons: { Todo: "lucide-circle", Done: "lucide-circle-check" } }`.

<a id="add_fields"></a>
## `add_fields`

**v2 shape:** the `fields` key on the item that reads the field.

v1 adds fields to the list query for the whole list. v2 adds a field only for the item that reads it:

- A `badge` function reads its own column. Put each other field it reads in the column's `fields`.
- A row action reads the fields in its own `fields`.

The list query fetches them. A field the reader may not read is left out.

Before (`automation_trigger_queue_list.js`):

```js
add_fields: ["run_after"],
```

After:

```js
// statusBadge(row) reads row.status and row.run_after.
page.columns.update("status", { fields: ["run_after"], badge: statusBadge });
```

Drop an `add_fields` entry that no v2 item reads. For example, `contact` added `image`, and the v2 file reads no image.

<a id="filters"></a>
## `filters`, `order_by`

**v2 shape:** `views/list.json`, with no JS.

Put the default filters, sort and columns in `<doctype>/frontend/views/list.json`. The file is a bare settings object. The site's and the person's saved settings win over it, key by key.

Before (`event_list.js`):

```js
onload: function () {
	frappe.route_options = { status: "Open" };
},
```

After (`event/frontend/views/list.json`):

```json
{
 "filters": [["status", "=", "Open"]]
}
```

`order_by` becomes `sort`. `error_log/frontend/views/list.json`:

```json
{
 "sort": [{ "fieldname": "creation", "direction": "desc" }]
}
```

A default column list uses `columns`, such as `[{ "fieldname": "title", "width": "200px" }]`. `quick_filter_fields` names the quick filters.

To change the filters or sort from a script at run time, set `page.filters` or `page.sort`. Setting either loads the rows again.

<a id="hide_name_column"></a>
## `hide_name_column`

**v2 shape:** `views/list.json` `columns`.

The v2 list draws the columns in its settings. Leave `name` out of `columns`. A doctype whose title field leads the default columns needs no change. `document_naming_rule` is an example.

<a id="disable_comment_count"></a>
## `disable_comment_count`

**v2 shape:** `views/list.json` `columns`. The list reads comment counts only when the `_comments` column shows. Leave `_comments` out of `columns` (`permission_log`, `recorder`).

<a id="has_indicator_for_draft"></a>
## `has_indicator_for_draft`, `has_indicator_for_cancelled`

No v2 key. frappe's own list scripts do not use them. A `docstatus` column draws a Draft, Submitted or Cancelled badge: add `{ "fieldname": "docstatus" }` to `views/list.json` `columns`. For other words or colors, put a `badge` function on a column and add `docstatus` to its `fields`.

<a id="onload"></a>
## `onload`

**v2 shape:** `onRefresh(page)`, but only for work that needs no server read.

v1 `onload` runs once and often adds buttons. In v2, add every item in `onRefresh`. The page clears its surfaces and runs `onRefresh` again on each pass, so an item added in `onRefresh` stays.

Sort the v1 `onload` body into three groups:

1. A button or menu item: add it in `onRefresh`. See [`add_inner_button`](#add_inner_button) and [`add_action_item`](#add_action_item).
2. Default filters through `frappe.route_options`: move them to `views/list.json`. See [`filters`](#filters).
3. A server read that changes what draws (a count, a status, filter options): no v2 shape on a cold load (gap). Show the action always and let its `run` do the work.

A value that boot already holds needs no read. Read `currentSession()` (from `@framework/ui`: the user's defaults), `page.roles` or `page.perms` in a `when`. `email_queue` showed **Suspend Sending** or **Resume Sending** from the `suspend_email_queue` default. The v2 port reads the default from the session:

```js
page.header.add({
	name: "suspend_sending",
	label: __("Suspend Sending"),
	when: (page) => isSystemManager(page) && !isSuspended(),
	run: (page) => toggleSending(page, 0),
});
page.header.add({
	name: "resume_sending",
	label: __("Resume Sending"),
	when: (page) => isSystemManager(page) && isSuspended(),
	run: (page) => toggleSending(page, 1),
});

// The session's defaults hold the value from boot; a toggle here outdates them.
const suspendedNow = ref(null);

function isSuspended() {
	return suspendedNow.value ?? Number(currentSession()?.defaults?.suspend_email_queue) === 1;
}
```

`error_log` showed **Flush Queued Error Logs** only when a queued count was above zero. `recorder` showed **Start** or **Stop** from `frappe.recorder.status`. These states need a server read, so both v2 ports show the actions always.

<a id="refresh"></a>
## `refresh`

**v2 shape:** `onRefresh(page)`.

v1 `refresh` runs after each data load. v2 `onRefresh` does not run on a filter, sort or Load More change. Do not use it to react to new rows.

`email_queue` added its buttons in `refresh`. The v2 port adds them in `onRefresh`.

A v1 `refresh` that edits the DOM, such as `rq_worker`'s empty-state text through `$no_result`, has no v2 shape (gap).

<a id="before_render"></a>
## `before_render`

No v2 shape (gap). frappe's own list scripts do not use it. Move the work to a `badge` function or to `views/list.json`.

<a id="button"></a>
## `button`

**v2 shape:** a row action, with `page.rowActions.add(item)`.

A row action takes `name`, `label`, `icon`, `right`, `fields`, `when(page, row)` and `run(page, row)`. v1 `show` becomes `when`. v1 `get_label` becomes `label`. v1 `action` becomes `run`. v1 `get_description` has no v2 key. A `when` that throws hides the action on that row.

Before (`todo_list.js`):

```js
button: {
	show: function (doc) {
		return doc.reference_name;
	},
	get_label: function () {
		return __("Open", null, "Access");
	},
	action: function (doc) {
		frappe.set_route("Form", doc.reference_type, doc.reference_name);
	},
},
```

After (`todo/frontend/list.js`):

```js
page.rowActions.add({
	name: "open_reference",
	label: __("Open Reference"),
	icon: "lucide-external-link",
	fields: ["reference_type", "reference_name"],
	when: (page, row) => Boolean(row.reference_type && row.reference_name),
	run: (page, row) => page.open(row.reference_type, row.reference_name),
});
```

A row action that opens a v1-only page has no v2 shape (gap). `dashboard` opens `dashboard-view`, and `workflow` opens `workflow-builder`.

<a id="formatters"></a>
## `formatters`

**v2 shape:** only for a few cases.

- A formatter that escapes text needs no port. v2 cells escape text. `file` is an example.
- A Date or Datetime format becomes `format`, a dayjs format: `page.columns.update("due_date", { format: "D MMM, hh:mm a" })`.
- One icon before any non-empty value becomes `icon`: `{ icon: "lucide-calendar" }`.
- A value-to-text map with no badge has no v2 shape (gap). `data_import` maps `import_type` to "Insert", "Update" and "Upsert". A `badge` function can change the label, but it then draws a badge.

<a id="prepare_data"></a>
## `prepare_data`

No v2 shape (gap). `user` sets an avatar in `prepare_data`. A `badge` function reads the row, but it cannot change the row.

<a id="primary_action"></a>
## `primary_action`

**v2 shape:** a header item, and `page.header.hide("new")` when the v1 action replaced **New**.

The list header's right zone holds the `new` button (label "Create"). Add your own item with `run`, and hide `new` when the v1 action replaced it. Hiding `new` also stops `list.create`.

```js
page.header.hide("new");
page.header.add({
	name: "new_print_format",
	label: __("New Print Format"),
	display: "button",
	right: "create",
	run: async (page) => {
		const values = await page.dialog.form({ title: __("New Print Format"), fields: [/* ... */] });
		if (values) await page.call("my_app.api.make_print_format", values);
	},
});
```

`communication` opens the v1 email composer. v2 has no composer for a new email from the list (gap).

<a id="get_form_link"></a>
## `get_form_link`

No v2 shape (gap). A row opens its own record. `print_format` and `workflow_action` change where a row opens. To keep the other target, add a row action that calls `page.open(doctype, name)`.

<a id="set_title"></a>
## `set_title`

No v2 shape (gap). The header's left zone holds the `module` and `doctype` crumbs. `todo` set the title "To Do", and the v2 port drops it.

<a id="calendar"></a>
## Calendar view hooks (`*_calendar.js`)

No v2 shape (gap). frappe ships only the List and Cards view types. Keep the calendar file for desk v1.

<a id="add_action_item"></a>
## `page.add_action_item`, `page.add_actions_menu_item`

**v2 shape:** a bulk action, with `page.bulkActions.add(item)`.

While rows are selected, a bar takes the controls row's place. A script item goes first in its **More** menu, under the doctype's name. The item takes `name`, `label`, `icon`, `run(page, names)`, `right`, `when` and `palette`. `run` gets the selected names as they were at the press.

Before (`contact_list.js`):

```js
listview.page.add_action_item(__("Download vCards"), download_vcards, false, "id-card");
```

After (`contact/frontend/list.js`):

```js
page.bulkActions.add({
	name: "download_vcards",
	label: __("Download vCards"),
	icon: "lucide-id-card",
	run: (page) =>
		postDownload(DOWNLOAD_VCARDS, { contacts: JSON.stringify(page.selection) }),
});
```

`postDownload` is a plain function in the same file. It submits a hidden form with the CSRF token, so the browser saves the file.

An action that changes records on the server uses `page.callSelected`. See the next section.

<a id="call_for_selected_items"></a>
## `listview.call_for_selected_items`, and a bulk `frappe.call`

**v2 shape:** `page.callSelected(method, args)` in a bulk action.

`page.callSelected` runs a **record function** once for each selected record, through the bulk runner. The runner owns the `bulk_actions` switch, the cap, the background run above the threshold, progress, and the result. It reloads the list when the run ends.

The record function must:

- Be whitelisted for `POST`: `@frappe.whitelist(methods=["POST"])`.
- Take `(doctype, name, **args)`, with a type on each argument.
- Check the record's permission itself, with `check_permission` or a save that checks it. The runner checks only the whitelist and the HTTP method.
- Return nothing, or `"queued"`. It raises to fail the record. Its `frappe.msgprint` messages are dropped.

A v1 method that takes a list of names needs a per-record wrapper.

Before (`communication_list.js`):

```js
let method = "frappe.email.inbox.create_email_flag_queue";
list_view.page.add_menu_item(__("Mark as Read"), function () {
	list_view.call_for_selected_items(method, { action: "Read" });
});
```

After, the wrapper (`frappe/email/inbox.py`):

```py
@frappe.whitelist(methods=["POST"])
def mark_read_unread(doctype: str, name: str, action: str) -> None:
	"""The list page's Mark as Read / Unread, one Communication per call of the bulk runner."""
	create_email_flag_queue([name], action)
```

After, the script (`communication/frontend/list.js`):

```js
page.bulkActions.add({
	name: "mark_as_read",
	label: __("Mark as Read"),
	icon: "lucide-mail-open",
	run: (page) => page.callSelected("frappe.email.inbox.mark_read_unread", { action: "Read" }),
});
```

`deleted_document` follows the same pattern. v1 called `bulk_restore(docnames)` and built a summary dialog. v2 calls `restore_record(doctype, name)`, which calls `restore(name, alert=False)`. The shell's result panel replaces the summary dialog.

`email_queue` wraps `retry_sending(queues)` in `retry_record(doctype, name)` the same way.

`page.callSelected` resolves `true` when the runner took the request. It resolves `false` after a toast when the runner refused it. With no row selected, it sends nothing. A Server Script API is not supported as the method.

<a id="add_inner_button"></a>
## `page.add_inner_button`, `page.add_menu_item`

**v2 shape:** a header item, with `page.header.add(item)`.

The list header's right zone holds `new` and the `⋯` menu. An item with no `display` is an entry in `⋯`. `display: "button"` draws a button. The item's `run(page)` gets the list page. Use `when(page)` to show the item only to some readers. Keep `when` synchronous and do not call the server in it.

Before (`rq_job_list.js`):

```js
if (!has_common(frappe.user_roles, ["Administrator", "System Manager"])) return;

listview.page.add_inner_button(
	__("Remove Failed Jobs"),
	() => {
		frappe.confirm(__("Are you sure you want to remove all failed jobs?"), () => {
			frappe.xcall("frappe.core.doctype.rq_job.rq_job.remove_failed_jobs");
		});
	},
	__("Actions")
);
```

After (`rq_job/frontend/list.js`):

```js
page.header.add({
	name: "remove_failed_jobs",
	label: __("Remove Failed Jobs"),
	when: (page) => page.roles.includes("System Manager"),
	run: async (page) => {
		const sure = await page.dialog.danger({
			title: __("Remove Failed Jobs"),
			message: __("Are you sure you want to remove all failed jobs?"),
			confirmLabel: __("Remove"),
		});
		if (!sure) return;
		await page.call("frappe.core.doctype.rq_job.rq_job.remove_failed_jobs");
		page.reload();
	},
});
```

A v1 menu item that acts on the selected rows is a bulk action in v2, not a header item. See [`add_action_item`](#add_action_item).

A control in the controls row (`page.controls`) with `run` also draws as a button. Use it for an action that belongs next to the filter and sort controls.

<a id="frappe_call"></a>
## `frappe.call`, `frappe.xcall` inside an action

**v2 shape:** `page.call(method, params)`. It returns a promise of the method's result: `const count = await page.call(method, values)`. A method that returns nothing resolves `null`.

Call the server only inside a `run`. Do not call it in `onRefresh` or in `when`. For a call on the selected rows, use `page.callSelected`.

<a id="listview_refresh"></a>
## `listview.refresh()`

**v2 shape:** `page.reload()`. It loads the rows again.

`page.refresh()` runs `onRefresh` again. Use `page.reload()` after an action that changed records. `page.callSelected` reloads the list itself.

<a id="dialogs"></a>
## `frappe.confirm`, `frappe.prompt`, `new frappe.ui.Dialog`

**v2 shape:** `page.dialog`. Every verb resolves `null` when the reader dismisses the dialog, so `if (!result) return` is the pattern.

| v1 | v2 |
| --- | --- |
| `frappe.confirm(message, yes)` | `await page.dialog.confirm({ title, message, confirmLabel })` resolves `true` |
| A confirm for a destructive action | `await page.dialog.danger({ title, message, confirmLabel })` draws it in red |
| `frappe.prompt(fields, callback)` | `await page.dialog.form({ title, fields })` resolves the values |
| `new frappe.ui.Dialog({ fields, primary_action })` | `await page.dialog.form({ title, fields, defaults, submitLabel })` |
| A dialog with a custom body | `await page.dialog.open(component, props, { title })` |

A `page.dialog.form` field takes `fieldname`, `fieldtype`, `label`, `options`, `reqd`, `read_only`, `hidden`, `depends_on`, `mandatory_depends_on`, `read_only_depends_on`, `description` and `child_fields` (the columns of a Table MultiSelect). It does not take `onchange`. A v1 dialog that changes its fields from an `onchange` (`user_permission`'s **Add / Update**) has no v2 shape (gap). Use `depends_on` where it is enough.

v1 `user_permission` **Bulk Delete** opened a `frappe.ui.Dialog` whose `primary_action` called `frappe.confirm`, then `frappe.xcall`. The v2 port (`user_permission/frontend/list.js`):

```js
const values = await page.dialog.form({
	title: __("Clear User Permissions"),
	fields: CLEAR_FIELDS,
	submitLabel: __("Delete"),
});
if (!values) return;
const sure = await page.dialog.danger({
	title: __("Clear User Permissions"),
	message: __("Delete every User Permission of {0} on {1}?", [values.user, values.for_doctype]),
	confirmLabel: __("Delete"),
});
if (!sure) return;
```

<a id="show_alert"></a>
## `frappe.show_alert`, `frappe.msgprint`

**v2 shape:** `page.toast.success(message)`, `page.toast.error(message)` or `page.toast.info(message)`.

```js
await page.call(`${ERROR_LOG}.flush_error_logs`);
page.toast.success(__("Queued Error Logs flushed"));
```

A v1 `msgprint` that sums up a bulk run needs no port. The shell shows the outcome of `page.callSelected`.

<a id="frappe_datetime"></a>
## `frappe.datetime`

**v2 shape:** `dayjs` from `frappe-ui`, with the session timezone from `@framework/ui`.

There is no `frappe.datetime`. A Datetime value is on the system clock. Parse it with the session timezone, as the `automation_trigger_queue` and `web_form_request` ports do.

Before:

```js
label = __("Scheduled for {0}", [frappe.datetime.str_to_user(doc.run_after)]);
```

After:

```js
import { currentSession } from "@framework/ui";
import { dayjs } from "frappe-ui";

const zone = currentSession()?.timezone;
const runAfter = (zone ? dayjs.tz(row.run_after, zone) : dayjs(row.run_after)).toDate();
const when = runAfter.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
```

For "now" on the system clock, use `zone ? dayjs().tz(zone) : dayjs()`. For a column's display format, use the column's `format` key and write no code.

<a id="set_route"></a>
## `frappe.set_route`

**v2 shape:** `page.open(doctype, name?, { view }?)`.

`page.open` opens a record, the doctype's list, or one of its saved views. Do not push a route yourself. See [`button`](#button) for an example.

<a id="realtime"></a>
## `frappe.realtime.on`

No v2 shape on the list page (gap). `data_import` listened for progress events and refreshed the list. The v2 port draws only the status badge.

<a id="set_indicator"></a>
## Page indicators, retention messages and auto refresh

No v2 shape (gap). Each of these needs a server read on a cold load, or a timer with no teardown hook:

- `page.set_indicator` (`error_log`, `recorder`, `rq_job`).
- `show_log_retention_message` (the log doctypes).
- Auto refresh on an interval (`recorder`, `rq_job`).
- Filter options filled from the server (`module_def`, `rq_job`).

Leave them out of the v2 file.

<a id="gaps"></a>
## Gaps

These v1 features have no v2 shape. Leave them out of `list.js`. Desk v1 keeps them.

- Badge theme `purple` (`automation_trigger_queue`). The port uses `blue`.
- A badge on the Check, Rating, Color, Attach, Attach Image or Image column itself (`error_log`, `user`, `user_type`, `note`, `web_form`, `web_page`, `workflow`). Put it on another column.
- A value-to-text cell map with no badge (`data_import` `formatters.import_type`).
- `prepare_data` (`user` avatar).
- `before_render`, `has_indicator_for_draft`, `has_indicator_for_cancelled` as keys.
- `get_form_link`, a row link target (`print_format`, `workflow_action`).
- `set_title` (`todo`).
- `button.get_description`.
- The calendar view (`*_calendar.js`, `calendar_view`).
- v1-only pages as targets (`dashboard-view`, `workflow-builder`).
- The email composer as `primary_action` (`communication`).
- A dialog field `onchange` (`user_permission` **Add / Update**).
- `frappe.realtime` on the list page (`data_import`).
- Any server read on a cold load: page indicators, retention messages, state-driven labels, filter options, OAuth return messages from `frappe.route_options` (`email_account`).
- Auto refresh on an interval (`recorder`, `rq_job`).
- DOM edits such as the empty-state text (`rq_worker`).
- The help video, `frappe.help.youtube_id` (`workflow`, `user`, `email_account`).
