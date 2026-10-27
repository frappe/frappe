# Desk v2 architecture

This file is the map of desk v2: the layers, the concepts each layer keeps, and the
main flows. It covers `frontend/`, `ui/`, `frappe/shell/`, and the framework code and
DocTypes the desk calls. A new reader can learn the whole desk from it in about an hour.

It describes the **target**: the code as it will be once the accepted cuts land. Where
today's code is not there yet, [Where the code is not there yet](#where-the-code-is-not-there-yet)
lists each gap and the change that closes it. That list gets shorter; nothing else in
this file waits on it.

What lives elsewhere, and is not repeated here:

| File | Holds |
| --- | --- |
| [`PHILOSOPHY.md`](./PHILOSOPHY.md) | The reasons: the `DP` principles behind these choices |
| [`CONTEXT.md`](./CONTEXT.md) | The words: what a record page, a contribution, a surface mean |
| [`SCRIPTING.md`](./SCRIPTING.md) | What `page` offers a script, region by region |
| [`COMPATIBILITY.md`](./COMPATIBILITY.md) | What a script can rely on across an upgrade |
| [`CLAUDE.md`](./CLAUDE.md) | Commands, formatting, and traps |

## How this file changes

- **A new concept needs a ruling.** A name that is not on its layer's list is either a
  cut or a new decision. The decision is made in a ticket, and the same PR that adds the
  code adds the name here. A build PR does not mark the rows it builds *New* or *Changed*.
- **A removed concept leaves in the PR that removes it.** So does a row in the gap list.
- **A new layer, or a new "may use" edge between layers, needs a ruling.**
- **Line count is never a measure here.** Simple means few concepts, one way to do each
  job, few files per flow, and no layer that uses a layer above it.

## The layers

There are nine layers. **Each layer may use only the layers below it.** "Use" means a
static import or a direct call. A lower layer may run a function that a higher layer
registered with it, such as a script's handler or a page's save. That is a callback, not
a break: the lower layer owns the contract, and the higher layer fills it.

Browser code reaches server code only through `/api/v2` requests and the realtime socket.
The HTML page, the JS files and the icon sprite are static files.

| # | Layer | Holds | Where | May use |
| --- | --- | --- | --- | --- |
| 9 | Customization | Code an app or a site adds: file scripts, stored scripts, list and item files | App folders; `Client Script` rows | Only the [import list](#9-customization), and the `page` object it is handed |
| 8 | Pages | The index, list page, record page and its parts; pages an app contributes | `frontend/src/pages/`; app `frontend/pages/` and replacement pages | 1 to 7 |
| 7 | Page engines | The record page engine and its `page` object; the list engine; the script loader | `frontend/src/recordPage/`, `frontend/src/list/` | 1 to 6 |
| 6 | Shell | Rail, sidebar, navigation, router, page frame, page states, composer window, socket | `frontend/src/shell/`, `navigation/`, `router/` | 1 to 5 |
| 5 | Desk services and registry | Boot data, addresses and `routeFor`, translations, icons, arrangement, browser memory; the registry of everything an app adds | `frontend/src/` root modules, `icons/`, `contributions/`, `acts/` | 1 to 4 |
| 4 | `ui` components | Fields, forms, lists, filters, the activity feed, the composer, upload | `ui/src/components/`, `ui/src/experimental/`, `ui/island/`, the other composables | 3, and 1 through it |
| 3 | `ui` data | Requests, the data cache, the socket rooms, the session, meta, permissions | `ui/src/api/`, `ui/src/cache/`, `ui/src/socket.ts`, `ui/src/utils/`, the four data composables | 1 |
| 2 | Desk server | The shell page, boot, the address table, navigation, arrangement, app prefixes | `frappe/shell/` | 1 |
| 1 | Framework server | Documents, permissions, REST API v2, the desk v2 DocTypes, the record address | `frappe/` outside `frappe/shell/` | nothing above it |

The four data composables are `useSession`, `useDoctypeMeta`, `useDocPermissions` and
`useUserRoles`.

Three things sit outside the nine layers:

- **`frontend/src/main.ts` sits above all of them.** It wires every layer at start-up,
  and nothing imports it. It is the only file that may use every layer.
- **The build sits beside them.** It reads app folders and writes the registry file and
  the import map. The running desk never imports it. The build is `frontend/plugin/`,
  `frontend/vite.config.js`, `frappe/bundler.py`, and the manifest code the bundler needs.
  The architecture page in `frontend/architecture/` sits beside it too: it reads the code
  and this file, and the running desk never loads it.
- **The template compiler sits beside them.** It turns each `template:` string in a script
  into a render function. It is `frontend/templateCompiler/`: the compile module and the
  names file. The build imports it for app files. The framework server runs it with `node`
  for stored scripts, from `client_script.py` only. `main.ts` imports only its names file.
  It uses its own files and the npm packages in `frontend/node_modules`, and nothing from
  a layer or the build.

### `ui/` stands on its own

`ui/` (the `@framework/ui` package) is a library for every Frappe app, not a part of the
desk. Layers 3 and 4 may use only the framework server through REST API v2, their own npm
dependencies, and their own files. They never use `frappe/shell/`, `frontend/`, desk boot
data, or record page words.

- **The desk passes in what only the desk has**: the session, the CSRF token, the socket,
  upload limits, the invite address, Create through `CreateRecordKey`, and record pages
  through `RecordLinkKey`. `ui/` works, with a sensible default, when an app passes none
  of them.
- **Judge `ui/` by what it exports**, not by what the desk imports. "No app uses it
  today" is never a reason to cut or change something in `ui/`.
- **The concept lists use the root index and the named subpaths** in `ui/package.json`.
  The desk imports `ui/` only through them: the lint in `frontend/eslint.config.js` refuses
  any other `@framework/ui/` path in `frontend/src`, a `vi.mock` target included. The
  `"./*"` entry stays for now, so an app can still import any file. No export carries a
  promise yet. The @framework/ui map decides the public surface.
- **A `ui/` name is a concept row only when it is public**: the root or a named subpath
  exports it, and code outside `ui/` imports it. Any other `ui/` name is internal and gets
  no row. The structure check works this out and counts internal names apart from gaps.
- **`ui/` has its own tools for apps**: `ui/vite`, the vite plugin for an app that uses
  `@framework/ui`, and `ui/island`. They are not part of the desk build.

### Why the record page engine and the pages are two layers

The engine (layer 7) builds `page` and draws nothing. The record page (layer 8) draws, and
fills the engine's `RecordPageHost` contract with its load, save, tabs and feeds. A
script talks to the engine, so a page can be replaced without changing what a script
sees.

## Concepts by layer

Each layer has a **closed list**. A concept is a name a reader must learn: an exported
API, a store, a cache, a registration point, a hook, a lifecycle event, a DocType, or a
route only desk v2 uses. A helper used by one file is not a concept. A family of names
learned together is one row.

A concept that is also a word in [`CONTEXT.md`](./CONTEXT.md) links to its entry there.
The row says only what the code adds to that word.

Rows marked *new* do not exist in code yet. Rows marked *changed* exist, but an accepted
cut or a `ui/` change reshapes them.

### 1. Framework server

| Concept | What it is |
| --- | --- |
| [`Rail`](./CONTEXT.md#rail) | The DocType behind the rail: one record per app, with site and per-user copies |
| [`Sidebar`](./CONTEXT.md#sidebar) (`navigation_items` table) | A sidebar per module or doctype. Desk v2 reads `navigation_items`; desk v1 reads `items` |
| [`Navigation Item`](./CONTEXT.md#navigation-item) | A row's fields: key, parent, type, target, label, icon, anchors |
| [`Navigation Item Type`](./CONTEXT.md#navigation-item-type) | Holds the rule for who can see a row of that type |
| [`Settings Dialog`](./CONTEXT.md#settings-dialog-doctype) | One app's layer of the settings dialog, addressed like `Rail`. An `extends` record adds blocks to a host's panes and no pane. Only developer mode or a system write sets the app layer |
| [`Settings Pane`](./CONTEXT.md#settings-pane) and [`Settings Block`](./CONTEXT.md#settings-block) | The two row types: a pane's key, label, icon and description; a block's key, pane, [binding](./CONTEXT.md#binding) or component, fields, named bindings, search settings, anchors and [save mode](./CONTEXT.md#save-mode). Keys are kebab-case, and a block key is unique in its merged pane |
| `Doctype View` | Saved list settings (columns, sort, quick filters), per person or per site |
| `Form Layout` | A stored layout for a doctype's Details, Side Panel, Quick Entry or New Record, with an optional condition. A Quick Entry or New Record row can also hold inline fields: DocField-shaped dicts beside the fieldnames, sent to the insert under their own names |
| [`Client Script`](./CONTEXT.md#client-script) with `view = Record` | The table that holds the record page's stored scripts |
| Client Script class check | On save, warns about CSS classes the build does not define. Reads the build's `classes.json` |
| Client Script template compile | On save, compiles a script that holds `template:` and blocks the save on an error. On fetch, sends the compiled copy from the Redis cache. On a cache miss, it compiles with one `node` call per doctype. The record keeps the source only |
| `code_only_modules` hook | Modules that hold only code. Their navigation goes to named heir modules |
| Layer resolution (`frappe.desk.layers`) | Merges base, site and user copies of a list and places items by anchors |
| Record address | The one address of a record under `/apps/<prefix>/`. `get_url_to_form`, emails and the desk all use it. *New: moves here from `frappe/shell/`* |
| Realtime events | `doc_update`, `docinfo_update`, `doctype_update`, `list_update`, `client_script_changed` |
| Doctype View routes | Get, save and reset a list's saved settings |
| `get_form_layouts` | A doctype's stored Form Layouts of one type. With no row, Quick Entry falls back to the Quick Entry fields (the mandatory ones, those marked for Quick Entry, and those with a mandatory condition), and New Record falls back to the Details rows. A Quick Entry read also returns the `dialog` flag: whether Create opens a dialog or the full page. The two create types accept the create right or read |
| `get_new_doc` | A new document of a doctype with its defaults, for a person with the create right. Nothing is saved |
| `search_records` (`frappe.desk.palette`) | The palette's records for a typed text: `search_widget` on the page's doctype, then on each Global Search doctype in order, each only where the user can read it. 3 per doctype, 10 in all, a record named exactly as typed first. No cache |
| `get_client_scripts` | A doctype's enabled stored scripts for one view, in run order, and whether the user may write scripts |
| `report_customization_error` | One rate-limited Error Log row when a script fails on the record page |
| `get_outgoing_senders` | The addresses the user may send email from |
| `get_boot_translations` | All translations for a language, cached by a version |
| `GET /api/v2/session` | The signed-in user and site defaults |
| Document parts routes | Add, remove or change one part of a record: assignments, shares, tags, favourites, follows, comments |
| `include=` parts | A record, meta or list read that also returns named parts |
| Activity route | A record's timeline entries in one read |
| Attachment routes | Upload a file, attach it to a record, or detach it |

### 2. Desk server

| Concept | What it is |
| --- | --- |
| `SHELL_ROOT` (`/apps`) | The address root that every desk v2 page lives under |
| Shell page | Serves the one built `index.html` for `/apps` and each claimed prefix, after a permission check. The website router finds it through the `page_renderer` hook |
| Built document cache | Keeps the built `index.html` in memory until its file changes |
| [`app_prefix`](./CONTEXT.md#prefix) hook | Where an app declares its prefix, for example `desk` |
| `app_modular` hook | Whether an app's record addresses include the module |
| Prefix registry | Map of prefix to app, cached per site, cleared on app install |
| Shell path helpers | Split an `/apps/...` path into prefix and rest, and find its app |
| `app_permission` hook | Who may enter an app's prefix. Missing means "is a System User" |
| `guard_prefix` | Sends a guest to login and a Website User to `/me`, and refuses anyone else without app permission. `/apps` is checked as frappe's |
| [Boot](./CONTEXT.md#boot) payload | Built by the server for each prefix |
| `app_boot` hook | An app adds its own boot keys. A failing one is dropped and logged |
| `add_to_apps_screen` hook | Title and logo of an app tile on `/apps` |
| Boot key limit | Logs any boot key, or key of the settings reply, over 100 KB |
| `metadata_version` | Boot key that changes when doctypes change |
| Address table | Each doctype and module mapped to its slug and owning app. One server cache key |
| [`slug`](./CONTEXT.md#slug) | The function that makes a doctype's slug |
| Address clash guard | Refuses a DocType or Module name whose slug clashes with a page |
| Reserved route guard | Refuses any website route that starts with `apps` |
| Prefix check on install | Refuses an app whose prefix is taken or malformed |
| Navigation resolution | Builds an app's rail and sidebars from base, site and user layers, filtered for the user |
| Cross-app extensions (`app:key`) | Another app's rail rows, merged in with namespaced keys |
| Settings merge (`resolve_panes`) | Every app's [panes](./CONTEXT.md#pane), each with its host's [blocks](./CONTEXT.md#block) and then extending apps' in `app_order`, anchored blocks moved. Drops an orphan block, a block bound to a doctype the site lacks, and an empty pane. Unfiltered, for one cache entry |
| Settings filter (`SettingsFilter`) | Drops the blocks a user may not use, the fields above their readable permlevel and the panes left empty, by the rail's role pass; marks unwritable fields read-only and builds the search label index from what is left |
| `get_panes` | The settings dialog's panes and label index for this user, and the title of each app it holds a pane of, read on first open. The merge is cached on `metadata_version` and on a digest of the `Settings Dialog` records' names and `modified`, so a save or delete rebuilds it |
| `places` (`frappe.shell.palette`) | The doctypes the user can read (`can_read`) in an app they may enter, each with its app, its address and `can_create`; the apps the user can open; and each app's title. Read on the palette's first open and held for the tab. No cache |
| Visibility rules (`NavigationContext`) | Decides per row whether the user may see it |
| `navigation_item_resolvers` hook | An app supplies the visibility rule for its own item type |
| Arrangement | Stores only the difference between a user's or site's order and the layer below |
| `get_boot` | The boot payload for a path |
| `get_addresses` | The address table, HTTP-cached on `metadata_version` |
| `get_contents` | The doctypes, reports and pages of an app or module that the user can read |
| Arrangement routes | Get, save or reset a rail or sidebar order |
| Index layer (`arrange`, `save_index_layer`) | The person's order and hidden apps on the [index](./CONTEXT.md#index), one JSON in user settings under `/apps`, cached per user in `_user_settings` and written to `__UserSettings` on each save, since a full cache clear drops that hash. The index boot puts the app layer's tiles in its order, an app it does not name last, and marks hidden ones. A save keeps only the person's own tiles; an order equal to the app layer's stores nothing, and Reset saves two empty lists |
| Index notices (`index_notices`, `read_whats_new`) | The index boot's notices. A System Manager gets one setup nudge while the site's setup wizard has apps to set up, with the wizard's address. A System Manager or Workspace Manager gets what's new: the title and new version of each app updated since `User.last_known_versions`, unless System Settings turns it off. The list is cached per user on a digest of the versions seen and installed, for a day, because `get_change_log` runs git per app. A person with none recorded has the current versions recorded, committed although the boot is a GET. Anyone else gets none and pays no query. `read_whats_new` returns the notes as HTML to those two roles and records the versions seen |

### 3. `ui` data

The list is what `ui/` exports from its root index and from the data subpaths: `api`,
`cache`, `socket`, `utils`, and one for each of the four data composables.

| Concept | What it is |
| --- | --- |
| Response envelope (`Envelope`, `ApiError`, `isApiError`, `readEnvelope`, `TIMESTAMP_MISMATCH`, `CodeError`, `FieldError`) | *Changed.* Every `/api/v2` reply is `{ data }`; every failure is one error class. A compile error carries `codeErrors`: the field, line, column and message of each error in a Code field's text. A refused save carries `fieldErrors`: each field it names, with its row in a child table |
| Request transport (`request`, `apiUrl`, `requestHeaders`) | The one fetch wrapper for `/api/v2`. Takes the CSRF token as a documented input or finds it itself. A caller may set the browser's cache mode |
| Document calls (`getDocument`, `getDocumentFields`, `listDocuments`, `countDocuments`, `searchDocuments`, `createDocument`, `updateDocument`, `deleteDocument`, `copyDocument`) | Read and write one record or a list. `getDocumentFields` reads some fields of one record and makes no list entry. `searchDocuments` can skip the browser's cached answer |
| Method calls (`runMethod`, `runDocumentMethod`) | Call a whitelisted method, or a method on one document |
| `getMeta` | Fetch a doctype's meta |
| Record parts (`getDocumentPart`, `addPart`, `removePart`, `updatePart`) | Read or change one named part of a record |
| Collaboration calls (`addAssignment`, `addShare`, `addTag`, `addFavourite`, `addFollow`, and each `remove`) | One pair of calls per side panel feature |
| Comment calls (`addComment`, `updateComment`, `removeComment`) | Post, edit and delete a comment |
| File calls (`uploadFile`, `attachFile`, `removeAttachment`, `downloadFile`) | Upload in chunks and attach to a record |
| Session calls (`getSession`, `logout`, `getTranslations`) | The signed-in user, sign-out, and translations |
| Data cache (`@framework/ui/cache`: `readCachedDocument`, `readCachedList`, `readCachedRows`, `clearDataCache`, `onRecordLeft`, `documentKey`, `listCacheKey`, `DocumentEntry`, `ListEntry`, `feedFieldRead`, `feedListError`, `holdDocument`) | The one in-memory store of records and list queries. Every reply goes into it, in the order the requests were sent. It keeps any read. It keeps 50 complete records while their replies add up to 32 MB or less, and it never drops the record read last, the open one. `feedListError` drops a list the server refused with a 403 or 404. `feedFieldRead` keeps a record that `getDocumentFields` read with no list, up to 200. `holdDocument` keeps an entry past every limit while a field on screen shows it. It tells a listener when a record's complete entry goes, and the Activity feed frees the rows it kept for that record |
| Session store (`@framework/ui/useSession`: `useSession`, `setSession`, `provideSession`, `currentSession`, `SessionKey`) | One shared session. The desk passes its own; `ui/` fetches one only when none is passed |
| Doctype meta store (`@framework/ui/useDoctypeMeta`: `useDoctypeMeta`, `DoctypeMeta`, `markDoctypeMetaStale`) | Fetches and holds each doctype's meta. On `doctype_update` it keeps the old meta on show and reads a fresh one. An empty doctype reads nothing |
| Permissions (`@framework/ui/useDocPermissions`: `useDocPermissions`, `FieldAccess`) | What the user may do with a record, from its read; the access to each field by permission level, and whether the roles hold a right on the doctype at level 0, from the meta's permission rows and the session's roles. For display only: the server enforces |
| Roles (`@framework/ui/useUserRoles`: `useUserRoles`) | The session user's roles, from the one shared session |
| Naming (`NEW_NAME`, `isNamedByPrompt`, `typedTextField`) | How a doctype names a new record: the insert key for a typed name, the prompt rule, and the field that typed text fills |
| Filter prefill (`equalityValues`) | The values a new record starts with from the equality filters it was created under. The list's Create and a Link field's Create both use it |
| Shared memo (`memoizedState`, `holdFresh`, `landFresh`) | One state per key, built once and shared by every caller. A stale memo's fresh value shows as soon as it arrives. While a page holds fresh values, they show together when it lets go, in the same step as the page's own reads |
| Scoped registry (`setScoped`) | Overrides a map entry for one Vue scope |
| Scroll landing (`landScroll`, `onScrollSettled`) | *New.* Puts a kept scroll offset back once the content is tall enough, and reports a scroll once it has stopped for 150 ms. The list and the record page keep their offsets with it |
| History state (`keepInHistory`) | *New.* Writes one key of the history entry's state, and survives a browser that refuses the write. The list, the record view and the shell's sidebar write through it |
| Socket input (`@framework/ui/socket`: `getSocketInstance`, `subscribeToDoc`, `resubscribeHeldDocs`, `RealtimeSocket`) | *Changed.* The app hands `ui/` its socket, and `ui/` joins record rooms on it. `ui/` warns when there is none. A reconnected socket joins the held rooms again |
| Translate function | *New.* `ui/`'s own `__`, which works without the desk's boot version |

### 4. `ui` components

The list is the rest of the root index and the named subpaths. Each row is a subpath or a
component group, with its main names.

| Concept | What it is |
| --- | --- |
| `FormLayout` (`@framework/ui/FormLayout`: `FormLayout`, `FormLayoutSchema`, `Tab`, `Section`, `Column`, `FieldNode`) | *Changed.* Draws a form from a tabs, sections, columns and fields tree. Works out field access itself. A host may hold the chosen tab and the open sections |
| Layout building (`buildLayoutFromMeta`, `compose`, `Decorator`, `mapField`, `fieldsToLayout`, `resolveLayout`, `resolveFieldConditionals`, `resolveTabConditionals`, `applyTabOverride`, `evaluateDependsOn`, `DROPPED_FIELDTYPES`, `identifyTabs`, `tabStripLabel`) | Turns meta fields into a layout tree, and applies depends-on, hidden and overrides for one document. `mapField` turns one meta field into a field node. `DROPPED_FIELDTYPES` are the fieldtypes the form never draws. `identifyTabs` gives each tab a stable name, unique in its strip, so the reader keeps their place when a tab comes or goes. `tabStripLabel` is the label the strip shows |
| Child rows (`useChildRowModel`, `newRowValues`, `NO_VALUE`, `ROW_ID`, `identify`, `rowKey`, `holdsChildRows`) | The rows of a child table field, a new row's default values, and the fieldtypes that hold no value. `identify` gives a row with no name a `ROW_ID`, and `rowKey` is the row's stable key, from its name or that id. `holdsChildRows` tells which fieldtypes hold rows |
| Value formatting (`formatField`, `formatNumber`, `formatCurrency`, `formatRating`, `flt`, `parseLongInt`, `getFormatDefaults`, `setFormatDefaults`, `useDocValueReader`, `resolveFieldCurrency`) | *Changed.* Formats numbers, currency and dates for display. `formatRating` shows a Rating as stars out of its star count (`3 / 5`), in a group-by cell and a panel row. `useDocValueReader` reads a Currency field's linked currency from the data cache, once per mount, and `resolveFieldCurrency` works out the currency a Currency field shows. `parseLongInt` keeps a Long Int past 2^53 as a digit string |
| Field types (`registerFieldType`, `getFieldComponent`, `focusField`; `useFieldTypes` from `FormLayout`) | Maps a fieldtype to the component that draws it. `focusField` puts the cursor in a field's cell, in a rich-text body before any input, and waits for a lazy control to draw |
| Form keys (`@framework/ui/fields/types` and `@framework/ui/FormLayout/types`, and `useRecordLink` from `@framework/ui/fields`: `DocKey`, `ParentDocKey`, `UpdateKey`, `ResolveFieldKey`, `LinkTitlesKey`, `CodeErrorsKey`, `FieldErrorsKey`, `fieldErrorKey`, `FieldAddress`, `FieldError`, `markedFieldnames`, `CreateRecordKey`, `RecordLinkKey`, `RecordLink`, `useRecordLink`) | *Changed.* How a field reads the document, writes a value, and shows link titles. `ResolveFieldKey` hands a field the component for a fieldtype. `CodeErrorsKey` hands a host's compile errors to its top-level Code fields, which show them as lint marks. A null value cuts them off, as the record page's dialogs do. `FieldErrorsKey` hands a host's field errors, keyed by `fieldErrorKey`, to every field and grid cell, and a null value draws none. The form's tab strip shows a red dot on each tab that holds a shown field `markedFieldnames` names. `CreateRecordKey` hands Link, Dynamic Link and Table MultiSelect fields the host's Create and create right; with none or null, they offer no Create, as in a filter's value input. `RecordLinkKey` hands Link and Dynamic Link fields the address of the record a value names and a way to open it, which `useRecordLink` reads; with none or null, as in a filter or a dialog, they open nothing |
| `TemplateNamesKey` | The component names a `template:` string can use with no `components:` entry. The Code field completes them. With no value, it completes Vue's built-in components only |
| Change reports (`warnMissingCommit`) | *Changed.* What replaces `CommitKey` once the commit channel moves to `frontend/`. How a form tells its host that a value or a child row changed. Optional: a form works without a host. `warnMissingCommit` warns, in development, when a form has no host to report to, since every report would then be lost |
| `Link` (`@framework/ui/Link`), `RecordAnchor`, `Grid`, `Phone`, `TableMultiSelect` (`TableMultiSelectExposed`, `TableMultiSelectSlots`) | Field controls with their own pickers and tables. A creatable `Link` keeps its Create row last, whatever is typed. A `Link` with an `href` shows an arrow to the record; `RecordAnchor` is that link, where a plain click asks the host to open the record and a modified click is the browser's. A creatable `TableMultiSelect` shows Create in its footer; its `focus` and `search` let `useLinkCreate` drive it as it drives `Link` |
| `ActivityTimeline` (`@framework/ui/ActivityTimeline`: `ActivityTimeline`, `useActivityTimeline`, `reloadActivityTimeline`, `addPendingActivity`, `compareActivities`, `TimeAgo`) | A record's activity feed, its row types, and one listener per record room for feed rows and docinfo. `TimeAgo` shows a time as "2 hours ago", with the full date on hover |
| `Composer` (`@framework/ui/Composer`: `CommentComposer`, `EmailComposer`) | Comment and email editors, and the payload each sends |
| `RichText` (`@framework/ui/RichText`: `uploadMedia`, `htmlToText`, `isEmptyHtml`; and `RichTextView`, which the index's what's new also draws; and `richTextKit`, `richTextToolbar`, which only `ui/` uses) | The rich-text setup the Text Editor field and the composer share: the editor kit and toolbar, an image upload over a `FileUpload` transport, and stored HTML drawn or read as text with no editor |
| `FileUpload` (`@framework/ui/FileUpload`: `FileUploadDialog`, also its own subpath to load it apart, `AttachmentsList`, `UploadTray`, `useUploader`, `defaultTransport`, `registerUploadSource`, `UploadLimitsKey`) | Upload dialog, attachment list and tray, with a swappable transport and limits that have a default |
| `Filter`, `QuickFilter`, `ConditionBuilder` | Edit list filters, and their address and wire format |
| `SortBy` | The list sort control and its `order_by` string |
| `ColumnSettings` | Pick, order and size list columns |
| `experimental/List` (`List`, `ListFooter`, `ListBulkBar`) | A virtual-scroll list with selection and a bulk bar |
| `ListView` and `usePagedList` | An app's own paged list: rows a page at a time |
| `useLinkSearch` | The server's matches for a link picker; the last answer wins. A fresh search skips the browser's cached answer |
| `Notifications` | The notification panel and its data |
| `InviteUser` | Invite users. The app passes the address to land on |
| `DataImport`, `Onboarding`, `SignupBanner`, `TrialBanner`, telemetry | App-level parts that know about a Frappe backend or Frappe Cloud |
| Islands (`@framework/ui/island`) | Mount a Vue island inside a page that desk v2 does not draw |

### 5. Desk services and registry

| Concept | What it is |
| --- | --- |
| [Boot](./CONTEXT.md#boot) (`Boot`, `fetchBoot`, `BootUnauthorized`) | Nothing draws before it |
| Navigation shapes (`NavigationItem`, `Navigation`) | One rail or sidebar row, and the rail plus every sidebar |
| Address table (`fetchAddresses`) | Each doctype's slug and module, keyed by `metadata_version` |
| Route builders (`routeFor`, `routeForModule`, `routeForNew`, `urlFor`, `isModular`) | Build a link to a list, a record, a new record with its prefill values, or a module. Honour page replacements |
| Shell slot (`registerShell`) | Holds boot, addresses and the router, so `routeFor` works without arguments |
| Arrangement (`fetchArrangement`, `saveArrangement`, `resetArrangement`, `move`) | Read, save and reset the order of rail and sidebar items |
| Create right (`useCreateRight`) | Whether the person may create a doctype's records, from the meta, the session roles and read-only mode. No request; the insert checks again. The doctype may change, and an empty one is never creatable |
| New record values (`fetchNewDocument`, `withNameField`, `fieldDefaults`, `fillEmpty`, `queryValues`, `typedValues`, `insertBody`) | What a new record starts with and sends, for the Create dialog and the new record page: the server defaults, the prompt-name field, the query values, the values "Edit full form" carries, and an insert body with no `name` |
| Module contents (`fetchContents`, `ContentEntry`) | What a module holds, filtered for the user |
| Translations (`loadTranslations`, `__`, `__n`, `installTranslate`) | Fetch the messages at start, translate a string or a plural, and put `__` and `__n` in every component template |
| Icons (`Icon`, the sprite) | One SVG sprite, loaded once, and the component that draws a symbol or an emoji |
| Latest reply wins | *New.* One helper for the desk's "only the newest answer counts" guards. `ui/` keeps its own, because it may not use this layer |
| Per-user browser memory (`browserMemory`, `tabMemory`, `BrowserMemory`) | One helper for every value kept in browser storage for one user: `browserMemory` for the browser, `tabMemory` for one tab. The composer's floating rectangle is the exception, because frappe-ui's `FloatingWindow` keeps it under its own key |
| `virtual:frappe/contributions` | The build's index of every app's contributed files |
| [Contributions](./CONTEXT.md#contribution) (`Contributions`, `DoctypeContribution`, `RecordHandlers`, `ActsContribution`, `actsFiles`) | Everything an app may add: doctype handlers, pages, item kinds, replacements, global acts. `actsFiles` holds each active app's `acts.js` loader in the site's app order |
| List handlers (`listHandlersFor`) | Per-doctype list changes, such as extra columns |
| Page registrations (`pages`, `replacementFor`, `registerStandardPages`, `standardPage`, `StandardPages`) | The page for each address. Standard pages are the default registration; an app's page replaces one. The last app wins |
| Item kinds and the item contract (`itemRenderers`, `ItemRenderer`, `Rendering`, `ItemContext`) | What an app's `item.js` implements to draw a navigation item. The last app wins |
| After-save registry (`registerAfterSave`, `runAfterSave`, `askReload`, `AfterSave`, `SavedBinding`) | What runs after a settings binding of a doctype saves, with the saved record and the fields sent. Apps register their own doctypes through `@shell`; a handler that throws is logged and the others still run. `askReload` shows the one "Reload to apply" toast when a save changed any of the fields given |
| Settings components (`settingsComponentFor`, `SettingsComponentContribution`) | The lazy component a settings block names, by app and name. A name with no file gives nothing and a warning, and the block is dropped |
| `registerContributions(appOrder)` | Runs once before the first route, in app order. Hands each file script to the script loader |
| [Act](./CONTEXT.md#act) dispatcher (`acts`, `ActDispatcher`, `ActScope`, `ActEntry`, `ActItem`, `ActFields`, `ActRight`, `ActArgument`, `ActOption`, `AvailableAct`, `ActDenied`, `doctypeRight`, `whenLoaded`) | The desk's one dispatcher. A page registers a scope: its act surfaces by name, its context, its right check and its hold; the shell and the list page register theirs the same way. `run` finds `<surface>.<item>` as drawn after the replay, checks that it is present, not hidden and allowed, and runs it in the scope's hold, or rejects with `ActDenied`. `perform` is the reader's way in: a click, the palette or a key. A denial shows a toast, and a failure goes to the scope. `available` lists the acts present, shown and allowed now, with their fields; `find` gives one of them by its full name and reads only its own surface. While a scope's acts still load, a name it does not hold yet waits for them. `doctypeRight` checks a right on a named doctype from its meta's level 0 rows and the session roles, for the page and the shell, and `whenLoaded` waits for a loading flag to clear. No request and no cache |

### 6. Shell

| Concept | What it is |
| --- | --- |
| `AppShell` | The root component: rail, sidebar, page area, and the hash dialogs. On the [index](./CONTEXT.md#index) it draws no rail and no sidebar, and `UserMenu` where the rail's foot would be, under a cell the index's notices bell is teleported into |
| `PageFrame` | The frame every page draws inside: header, scroll area, gutter, and a page state in place of the content |
| Page states (`FrameSkeleton`, `PageState`, `PageStateValue`, `failedState`, `NotFound`, `NothingToOpen`) | Loading, empty, empty with a filter, nothing to open, not found, no permission (naming the denied act when the page gives one), offline and failed. Offline and failed offer Try again; not found offers the app's home; nothing to open offers all apps. `failedState` picks the state a failed read shows, with the server's message as text. The list, record and new record pages share them |
| Rail and sidebar (`RailColumn`, `SidebarPanel`, `SidebarRow`, `SidebarEdge`) | Draw the rail, the sidebar tree and its drag edge. The rail's app menu and the edge draw from shell acts |
| `UserMenu` | The avatar menu: the profile, then the shell acts My settings and Theme, the page's own rows, then Desk v1 and Log out. The rail draws it at its foot, and the index in the same place |
| Page menu rows (`pageMenuItems`, `usePageMenuItems`, `PageMenuItem`) | Rows the page on screen adds to the avatar menu while it is mounted. The index adds "Arrange apps" |
| `CustomizeSidebarDialog` | Reorder and hide rail and sidebar items, per user or per site |
| Act keys (`ActKeys`, `OpenArgument`, `overlayOf`) | Binds the `key` of each act the dispatcher lists as available through `useKeyboardShortcut`, while `AppShell` is mounted. Its code loads apart from the cold-load chunk. A press runs the act through `perform`; on a shared combo a page act wins over a shell act, with a dev warning. In a dialog, a popover or a dropdown (`overlayOf`) a key runs nothing, and a combo with Mod or Ctrl still blocks the browser's own key; such a combo also fires in a field. Only acts with a `key` have their right read. A key on an act with an argument opens the palette at that act's argument step, through the `OpenArgument` `AppShell` passes |
| Hash dialogs (`useHashDialog`) | A dialog addressed by `#...` in the address, so Back closes it |
| [Settings dialog](./CONTEXT.md#settings-dialog) (`ShellSettingsDialog`, `SettingsAddressBook`, `fetchPanes`, `SettingsPane`, `SettingsBlock`, `SettingsBinding`, `registerSettingsBlocks`, `SettingsSearch`) | The hash dialog at the [settings address](./CONTEXT.md#settings-address). Its chunk loads on the first open. It reads `get_panes` then and holds the reply for the tab, by `metadata_version` and user. It lists the framework's panes, the current app's group and an addressed foreign app's group for that visit. A short address is replaced by the full one; one it cannot show keeps its hash and shows one message. `main.ts` registers the page layer's component that draws a pane's blocks; its chunk loads with the pane list. A block segment scrolls to the block and flashes it once the pane's bindings have loaded. Search above the pane list matches every app's panes, blocks and the reply's label index, with no request per query: the framework's and the current app's results first, then other apps'. A pick opens its pane, shows the field's tab, and scrolls to and flashes the field |
| Desk's after-save handlers (`registerDeskAfterSave`) | `fetchBoot` makes `boot.session.user` reactive and `main.ts` registers desk's handlers: the session user's `User` updates the name, image and follow setting on screen, and a change to language, time zone or a `System Settings` format shows one "Reload to apply" toast |
| [Command palette](./CONTEXT.md#row) (`ShellPalette`, `PaletteRow`, `paletteOpen`, `openPalette`, `registerPageRows`, `pageRows`, `paletteGroups`, `PaletteGroup`, `PaletteContext`, `pinnedRows`, `rank`, `loadPlaces`, `PlacesReply`, `DoctypePlace`, `openPlace`, `usePaletteScope`, `PaletteHighlight`, `records`, `findRow`, `askFlow`, `paletteArgument`, `openArgumentStep`, `usePaletteArgument`, `createOptions`, `paneOptions`) | One palette in the shell, opened by Mod+K anywhere but the rich-text editor and by the rail's search item; in-page state, never in the address. Its chunk loads on the first open. Its groups come in a fixed order, each building its own rows: Recent and This page on the empty query, then This page, Desk, Go to (8) and Create (5) ranked by the query, then Records (10) in the server's order. This page holds the acts `acts.available()` lists on every surface but the shell's, then the rows a page registers; Desk holds the shell surface's. Go to holds this app's rail and sidebar rows from boot, the doctypes and apps `places` returns, and the panes `get_panes` returns; Create holds New X for each doctype `places` marks `can_create`, run through `shell.create`. Each open asks for whichever of `places` and the panes the tab does not hold yet. Tab on a row that opens a doctype's list in this prefix narrows the palette to that doctype: a chip, and its records from the link search at their `urlFor` address, from 2 characters after 200 ms, the last answer winning; Backspace in an empty input, Esc or the chip's × leaves. A group that asks the server hears each query and each change of page through its `follow`, and an empty one while the palette is closed or narrowed: Records asks `search_records` from 2 characters, once the typing has paused for 200 ms, and aborts the question before; meanwhile it shows "Searching…", a `pending` row, and "Could not search records", a `disabled` row, when the server refuses. An act with `palette: false` is not drawn. Picking an act with an `argument` keeps the palette open at its argument step, which an act's key also opens: the act as the same chip, and its options under the argument's label, asked with an empty query at once, then after each 200 ms pause, the last answer winning, and ranked by the query as it is typed; Enter runs the act with the picked value, and Backspace in an empty input, Esc or the chip's × goes back to the first step. The step pins nothing. Rows pinned below the list stay in view under its scrolling part, in the same listbox, so the arrow keys reach them last: on a list or record page, "Find “<text>” in <doctype>" opens its list filtered on the title field, or the name; last, "Ask Flow: <text>" shows while Flow's launcher has set `data-flow="ready"` on the document element, and picking it dispatches the window event `flow:ask` with `{ text }`, as the palette imports nothing from Flow; a narrowed palette pins nothing. When the highlighted row leaves and rows arrive late, the first one takes the keyboard. A picked act runs through `acts.perform`. No server cache; the tab holds the replies |
| Recents (`recents`, `Recent`) | The last 20 places and records this user opened by any route, newest first, in `browserMemory`, re-read before each write so another tab's visits stay. A record keeps the saved title its page reports. The palette shows 5 and breaks ranking ties with them |
| [Shell surface](./CONTEXT.md#shell-surface) (`useShellActs`, `Shell`, `OpenSettings`, `colorSchemes`, `shellAct`, `shellMenu`, `useAppActs`) | The `shell` surface `AppShell` registers on the dispatcher, and `Shell`, what a shell act's `run` receives: `router`, `toast`, `call`, `run`, `create` and `openSettings`. Its acts: `all_apps`, `customize_sidebar`, `copy_link` and `toggle_sidebar` while the rail draws (the toggle only while a sidebar shows), and `open_settings`, `my_settings`, `theme`, `desk_v1`, `log_out` and `create` everywhere. The rail's app menu, the avatar menu and the sidebar's edge draw an act only while `shellAct` finds it, the one rule for whether a shell entry is drawn. `page.create()` and `page.openSettings()` run `shell.create` and `shell.open_settings`. In the palette `shell.create` asks for a doctype and `shell.open_settings` for a pane, from the places and panes the palette holds, and `shell.theme` for a scheme. No built-in shell act has a `right`. Each active app's `acts.js` is imported at idle after the shell's first paint, and its acts join the surface as `shell.<app>.<item>`; a palette opened or an app act run before then waits for the import. A shell act's `right` is `{ doctype, ptype }`; an app act with a bare ptype is ignored with a warning |
| Logout (`logout`, `LogoutDialog`) | End the session, and go to login with a way back |
| Composer state (`composerState`, `openComposer`, `closeComposer`) | Which record's composer is open, with which writer, docked or floating |
| Composer drafts | Unsent comments and emails, per record and writer |
| Composer registration | A record page registers its record, its dock and its writers, so the composer can outlive the page |
| `ComposerWindow` | The composer card, docked or floating |
| Create (`openCreate`, `CreateRequest`, `createRequests`, `registerCreateDialog`, `closeCreates`) | The one way to open Create for a doctype. The shell keeps the open requests above any page and closes them on a route change. `main.ts` registers the page layer's dialog that draws them, and hands `openCreate` and the create right to Link, Dynamic Link and Table MultiSelect fields through `CreateRecordKey`. A field's Create opens above the dialog it sits in |
| Socket (`createSocket`, `repairRooms`) | Opens the realtime socket and hands it to `ui/` |
| Item lookup (`rendererFor`, `renderingOf`, `labelOf`, `iconOf`, `itemContext`) | Draws an item through its kind's renderer |
| Current item (`navigationDestinations`, `currentFrom`) | Which rail item and sidebar the current address belongs to |
| [Landing](./CONTEXT.md#landing) (`landingOf`) | Where an app's or a module's bare address lands: the first item of the arranged rail, or the first row of the module's sidebar, that resolves to a route in this prefix; a rail module item counts only when its module lands. The router redirects `home` and `module` there from `boot.navigation`, with no request and before any page paints. With none, the address shows `NothingToOpen` |
| Section memory | Which sidebar sections a user opened or closed |
| Sidebar memory (`sidebarMemory`) | Which sidebar this tab last showed for an address, per user |
| Item tree (`buildTree`, `useItemTree`) | Turns flat navigation rows into a tree |
| Router (`createShellRouter`, `contributedRoutes`) | The route table from boot, addresses and page registrations. On the index it holds only `home`, which draws the index, and not found. `/<doctype>/new` is the `new-record` route: always the standard new record page, so the word `new` is reserved. A saved record named "new" stays at `/<doctype>/new/record` |
| Route history (`recordRouteHistory`) | Queues each `list` and `record` address the router lands on and sends the batch to `Route History` after 10 s with no visit, or at once, kept alive, when the tab hides. A change of query alone is no visit. The index's Recent reads it |
| Record link (`recordLink`) | *New.* What `main.ts` hands Link and Dynamic Link fields through `RecordLinkKey`: a record's `urlFor` address, or none for a doctype with no address, and a router push to it |
| Page loader (`mainPageFor`, `loadedPage`) | Loads the registered page for an address once the frame has painted (at once on a cold load or in a hidden tab): `FrameSkeleton`, or the page's own loading state, until the code is in, the failed or offline page state if it fails |

### 7. Page engines

**The list engine** (`frontend/src/list/`)

| Concept | What it is |
| --- | --- |
| `useListPage` | Everything a list page needs: meta, columns, filters, sort, rows, settings, delete, and the values a new record starts with |
| `useListRows` | Rows and a total for one query, a page at a time |
| List settings (`useListSettings`, `markListSettingsStale`) | Saved columns, sort and quick filters, per user or site. On `doctype_update` it keeps the old rows on show and reads fresh ones |
| Stored settings | Converts saved settings to live columns, sort and quick filters, and drops fields the user cannot read |
| List address (`queryFromAddress`, `addressFromQuery`) | How filters and sort are written into the address |
| List defaults | Default columns and sort for a doctype, with app columns |
| History list memory | Page size and scroll in the history entry, so Back lands in place |
| Rows memory | Rows and scroll per doctype for the session, so any return lands in place |
| `useScrollMemory` | Restores and saves the scroll from the two memories |

**The record page engine** (`frontend/src/recordPage/`)

| Concept | What it is |
| --- | --- |
| `createRecordPage` | Builds `page` and every surface for one record, fires events, runs the replay |
| `RecordPageHost` | *Changed.* The contract a page fills: document, save, tabs, feeds, composer, what a failed act does, and whether it restored the reader's view. A new record's host adds `isNew` and `onSaved`, which runs after `afterSave`. The engine draws nothing |
| Script registry | The registered handlers per doctype and source |
| [Source](./CONTEXT.md#source) context | Which source is registering or running now |
| [`Surface`](./CONTEXT.md#surface) | The class behind each list surface |
| Staging | Acts wait during a replay and appear at one commit |
| Paint gate (`LATE_LIMIT_MS`) | When the page first paints, how a late `onRefresh` or a first visit's `page.cached` fetch lands, when `onOpen` runs, and the one repaint for background reads on a return visit. `LATE_LIMIT_MS` (5 s) is the longest it waits for a late part |
| Cached reads | *New.* The engine behind `page.cached`: one fetch per key per visit, and a value kept while the record's complete entry stays in the data cache, up to 20 keys for each record and script |
| Held acts (`createHeldActs`) | One queue for the acts a script asks for during a replay (tab move, panel section open or close, field focus, feed scroll, composer open, settings open). They run after the commit |
| [Commit](./CONTEXT.md#commit) channel | Turns a field change into a handler key (`qty`, `items.qty`, `items.onAdd`) and runs it |
| [Field](./CONTEXT.md#field-overlay) and form tab overlays | Changes keyed by fieldname or tab identity |
| Header projection | Turns the header list into two zones, nesting and overflow |
| Frame and body projection | Orders frame bands and works out body column widths |
| Form join | Joins the Details layout with the parts a script adds |
| Form layout source (`useFormLayout`, `markFormLayoutsStale`) | One fetch per doctype and layout type; picks the matching row. On `doctype_update` it keeps the old rows on show and reads fresh ones |
| Script loader (`loadRecordScripts`, `addFileScript`) | One loader per doctype for file scripts and stored scripts. When a stored script changes, it keeps the old scripts until the new ones have all compiled, then swaps them in one step |
| Page permissions | Rights, roles and field access, ready before handlers run |
| Read-only guard | The proxy behind the [read-only view](./CONTEXT.md#read-only-view) |
| Error reports | One Error Log row per script failure, by tier |
| Page dialogs | The engine behind `page.dialog` |
| Field errors (`FieldErrors`) | The marks on a form's fields and row cells, from the mandatory check, a refused save's `fieldErrors` and `page.fields.setError`. A mark clears on its field's edit, at a save's start and on a replay. One made during a replay or a hold lands at its commit |
| Mandatory check (`missingRequired`) | Each mandatory field shown after `depends_on` and still empty, child rows included. A save and both form dialogs run it before they send |
| [Row handles](./CONTEXT.md#row-handle) | Refuse once their row is gone |
| Feed surfaces | The engine behind `page.activity` and `page.files` |
| Composer surface (`ComposerHost`) | `page.composer`, over a host that owns the composer state |
| Icon and prop hooks (`setIconSource`, `setDrawnProps`) | The record page hands the engine an icon lookup and frappe-ui's `Button` prop names when it registers. Both halves are one concept |

### 8. Pages

**Pages other than the record page**

| Concept | What it is |
| --- | --- |
| [Index](./CONTEXT.md#index) (`IndexPage`, `IndexSkeleton`, `AppTile`, `AppLogo`, `ArrangeApps`, `MoreAppsTile`) | The page at `/apps`: a filter box over one tile per `boot.apps` entry the person has not hidden, with no request. The box spans the first row's logos, three columns at least, and has focus on load. Typing filters by title, hidden apps too, Enter opens the selection or the first match, and Esc clears the box. A tile opens its route by a full load. A tile's menu hides it, or shows a hidden one the filter found. "Arrange apps" draws every app in a drag grid with an eye each, and Reset and Done store the user layer. When boot gives `more_apps` (a System Manager on a site that can install apps from Cloud Settings), a dashed "Get more apps" tile follows the last app: the filter never matches it, Arrange leaves it out, and it links out to desk v1's desktop at `?cloud_settings=1`, which opens the Cloud Settings dialog. `IndexSkeleton` draws while the page's code loads |
| Index selection (`Selection`, `Selectable`, `SelectionSection`, `selectableId`) | The one arrow-key movement over every section of the index, in page order. A section joins it with its items and its column count, draws an item as selected like a hover, and gives it `selectableId` as its element id, which the filter box names as its active descendant and scrolls into view |
| Index Favourites (`IndexFavourites`, `favouriteKey`) | The row of chips under the tiles: one per `boot.favourites` entry, the person's 8 latest favourite records they can still read, each with its app's logo and the record's title, opening the record's address by a full load. No row when there are none, or while the filter box holds a query. The chips are one section of the index selection |
| Index Recent (`IndexRecent`, `recentKey`) | One row per `boot.recent` entry under Favourites: the person's 5 latest distinct list and record addresses they can still open, each with the logo of the app it was visited in, its title, its kind and how long ago, opening the address by a full load. No section when there are none, or while the filter box holds a query. The rows are one section of the index selection |
| Index notices (`IndexNotices`, `WhatsNewDialog`, `tuckedNotices`, `readWhatsNew`) | One frappe-ui `Alert` card in the bottom-right corner per `boot.notices` entry: the site's setup nudge, which opens the setup wizard by a full load, and what's new, which opens a dialog that reads the release notes, and so records them seen. Closing a card tucks it into a bell above the avatar for the tab, in `sessionStorage`; a click on the bell brings the cards back. The chunk loads only when boot sends a notice |
| `MainPage` | Shows the registered page for a list or record address |
| Standard pages (`standardPages`) | The framework's own page for each address, which `main.ts` registers as the default |
| `List`, `DoctypeList`, list acts (`useListActs`) | The standard list page, built on `useListPage`. Its built-ins are acts on one `list` surface: `list.create` (the create right), `list.customize_quick_filter`, and `list.delete` while rows are selected (the delete right). Its buttons and menus draw from those items, and draw an item only when its right passes. Scripts get no verbs on it yet |
| `DeleteDialog` | Confirm a bulk delete and report failures |
| `CreateDialog` | One Create request: the Quick Entry form in a dialog that inserts on save, or the full-page new record when the server says the doctype gets no dialog |
| New record page (`NewRecord`, `UnsavedRecord`, `NotSavedBadge`, `openingKey`) | The full-page new record at `/<doctype>/new`. Builds the record from the server defaults and the query, shows the header and the New Record form only, inserts on the first save and replaces the address with the saved record's. Each address is a new opening |
| Settings blocks (`SettingsBlocks`, `PaneDrafts`, `BindingDraft`, `ComponentBinding`) | A settings pane's generated and component blocks, which the shell's dialog mounts. A component block gets one `ComponentBinding` per named binding over the shared draft; its fields are the doctype's fields no generated block on that draft draws, and its `commit()` queues them in `auto` mode and does nothing in `button` mode. A component block with no binding is outside the pane's dirty state. Each [binding](./CONTEXT.md#binding) gets one draft, read fresh when the pane opens and shared by its blocks; a missing Record starts from its defaults and inserts on its first save. Each field is a settings row with its ui control and a save mark. An `auto` block saves a field when its control commits, a `button` block from the Save bar or Ctrl/Cmd+S. A save sends only the changed fields and `modified`, one at a time per binding, and a change made meanwhile joins the next. A 417 is sent again when the other save left those fields alone, else the record page's conflict question opens. Leaving a pane with changes no save holds asks the record page's discard question |
| App pages | Pages an app contributes or uses as a replacement. They may import only the [import list](#9-customization) |

**The record page** (`pages/Record.vue`, `pages/record/`)

| Concept | What it is |
| --- | --- |
| Record page host (`Record.vue`) | Fills `RecordPageHost`: loads, saves, and wires layouts, feeds, tabs and the composer. `UnsavedRecord` is the second host, for a record before its first save |
| Host parts both hosts share (`FORM_CLASSES`, `projectRecordHeader`, `discardChanges`, `Confirm`, `runSave`, `useSaveKeys`, `useUnloadGuard`, `provideRecordCommits`) | The form's classes, the header row's projection, the "Discard unsaved changes?" question, the save from the header (Ctrl/Cmd+S is the `key` of `header.save`), the browser's question before a reload, the settings blocks' Ctrl/Cmd+S scoped to their dialog, and the commit channel and field errors |
| Field landing (`landOnField`, `landOnFirstMarked`, `tabOf`, `stopLanding`) | Moves a form to a field's tab and puts the cursor in it. The record page's focus and both form dialogs use it. `stopLanding` ends a landing still waiting for a lazy control, when a page unmounts |
| Visit (`Visit`) | One object per visit to a record. Ending it aborts its reads, and a reply that belongs to an old visit is dropped |
| Return-visit parts | *New.* Which record parts a return visit needs before it paints from memory |
| Record source | The load, the parts re-read, the save, and a cached read |
| Meta source (`awaitMeta`) | The doctype meta as one promise or its current value |
| Refetch merge | Merges a background re-read into the draft the reader is editing |
| Save conflict (`SaveConflict`, `confirmConflict`) | The error when someone else saved first, the fields the reader would lose, and the question the record page and the settings blocks ask |
| Save code errors (`SaveCodeErrors`, `codeErrorsError`, `shownInDialog`, `codeErrorFrames`, `CodeErrorFrame`, `CodeErrorsDialog`) | *New.* A save the server refused because a Code field's text does not compile. One dialog lists each error with the lines around it, and the Code field marks them until the next save |
| Live scripts | Re-runs the page's scripts when a stored script of its doctype changes |
| Record feeds (`RecordFeeds`) | The data behind `page.activity` and `page.files`, with the feed's first-paint functions |
| Record tabs (`RecordTabsHost`, `useRecordTabs`) | *Changed.* The four built-in tabs, and the tab named in the address or put back by the record view |
| Tab rows (`registerTabRows`) | The palette's "Go to tab" rows for this page, one per tab on the strip, moving the reader as `page.tabs.activate` does |
| Panel context (`PanelContextKey`, `DocInfo`) | What the built-in panel sections read |
| [Panel](./CONTEXT.md#panel) entries | Joins panel items with the Side Panel layout |
| Panel [disclosure](./CONTEXT.md#disclosure) | *Changed.* Which panel sections are open. It reports them as shown and takes them back for the record view |
| [Built-in](./CONTEXT.md#built-in) actions | Framework quick actions and menu rows, offered by right |
| Composer host (`composerHost`, `openWriterContext`) | Joins `page.composer` to the shell's composer, and gives a writer its record |
| Writers | *Changed.* One pipeline for the comment and email writers and their drafts |
| Body columns | Column widths and collapse, per user |
| Form tab memory | The last form tab per doctype, per user |
| Record view (`RecordView`, `recallView`, `viewKeeper`, `readOffsets`, `landOffsets`) | *New.* The reader's tab, form tab, sections, panel sections and scroll on a record, put back on a return visit. Kept in the history entry, and per record while its complete cache entry stays |
| Dock height | The docked composer's height, per user |
| Docinfo readers | Assignees, shares, tags, favourites and follow, and their actions |
| Remote search | Server search for the user and tag pickers; the last answer wins |

### 9. Customization

What an app author or a site's script author writes. [`SCRIPTING.md`](./SCRIPTING.md) is
the reference for each `page` member.

| Concept | What it is |
| --- | --- |
| File script (`record.js`) | An app's `export default { ... }` handlers for a doctype |
| Stored script | A [`Client Script`](./CONTEXT.md#client-script) row: the same module shape as a file script, run from the database |
| Tiers and [run order](./CONTEXT.md#run-order) | The owner app's handlers, then other apps' file scripts, then stored scripts. Later tiers win |
| `*` doctype key | Handlers that run on every record, before the doctype's own |
| [Handlers](./CONTEXT.md#handler) and `Handler` | `Handler` is the type of one handler |
| Lifecycle events | *Changed.* `onRefresh`, `onOpen`, `beforeSave`, `afterSave`, `onTabChange`, `onFormTabChange`, `onPost`. On a return that restores the view, `onOpen`'s view acts do nothing |
| Field change handler | A fieldname key runs when that field's value changes |
| Child [table handlers block](./CONTEXT.md#table-handlers-block) | Handlers under a table fieldname: field keys, `onAdd`, `onRemove` |
| `SAVE_VETO` | Throwing in `beforeSave` cancels the save and keeps the draft |
| [Document](./CONTEXT.md#record) (`page.doc`, `page.saved`, `page.isDirty`, `page.isNew`, `page.doctype`, `page.docname`) | `page.isDirty` says whether the draft differs from the saved copy. `page.isNew` is true until the first save, and `page.save()` then inserts, also with no changes |
| `page.meta` | The doctype meta, read-only |
| Rights (`page.perms`, `page.roles`, `page.fieldAccess()`) | The user's rights, roles, and field access |
| Page acts (`page.save()`, `page.reload()`, `page.refresh()`, `page.call()`, `page.create()`, `page.openSettings()`, `page.run()`, `page.router`, `page.toast`) | Save, re-read, re-run `onRefresh`, call a method, open Create for any doctype, open the settings dialog, run an act by name, navigate, show a toast. `page.create()` and `page.openSettings()` run the shell acts `shell.create` and `shell.open_settings`. `page.create()` gives the saved record, or `null` |
| `page.cached()` | *New.* Server data for `onRefresh`: the kept value at once, fetched once per visit |
| [Surface](./CONTEXT.md#surface) verbs (`add`, `hide`, `show`, `update`, `move`, `has`, `order`, `clear`, `Position`) | The same verbs on every list surface |
| [Built-in](./CONTEXT.md#built-in) item names | The names a script hides or moves: frame, body, tabs, panel sections, actions, writers |
| `page.quickActions`, `page.header`, `page.frame`, `page.body`, `page.tabs`, `page.panelSections` | The regions of the page around the form |
| `page.form`, `page.form.tabs`, `page.fields`, `page.rows()` | The Details form, its tabs, field properties, and child rows |
| `page.activity`, `page.files`, `page.composer`, `page.dialog` | The feed, the attachments, the writers, and dialogs |
| List file (`list.js`) | An app's changes to a doctype's list, such as extra columns |
| Item file (`item.js`) | An app's renderer for one kind of navigation item |
| Acts file (`acts.js`) | An app's global acts at `<module>/frontend/acts.js`: a default export that lists acts, each run as `run(shell, value)` |
| Settings component file (`frontend/settings/<name>.vue`) | An app's component for one settings block. Its chunk loads when a pane that holds the block opens. Its one prop, `bindings`, holds per named binding `doc`, `saved`, `meta`, `loading`, `error`, `isNew` and `commit()`; it edits `doc` and never saves a binding itself |
| Import list | The one list of names that customization code and app pages may import |

**The import list.** App files and stored scripts share one list:

| Name | What it gives |
| --- | --- |
| `vue`, `vue-router`, `frappe-ui` | The framework's shared packages |
| `@framework/ui` | All of `ui/` while the `"./*"` entry stays |
| `frappe/i18n` | `__` and `__n`. A script imports them. A `template:` string, and every other component template, gets both with no import |
| Desk names | `routeFor`, `routeForModule`, `urlFor`, `RouteOptions`, `isModular`, `ContentEntry`, and the after-save registry's `registerAfterSave`, `askReload`, `AfterSave`, `SavedBinding`. App files import them from `@shell` today; stored scripts cannot. The one module name is for Build and publishing to choose |
| App names | Names an app publishes through its `import_map` hook |

A script reaches the rest of the desk only through the `page` object it is handed.

### Outside the layers

**`main.ts`**

| Concept | What it is |
| --- | --- |
| Start sequence (`start`) | Boot, then translations and icons without waiting, and the Create dialog's registration, then addresses, contributions, standard pages, router, socket, and mount |
| What the desk hands `ui/` | The session, the CSRF token, the socket, upload limits, the invite address, Create for Link, Dynamic Link and Table MultiSelect fields through `CreateRecordKey`, record pages for Link and Dynamic Link fields through `RecordLinkKey`, the component names a template can use with no `components:` entry, and `__` and `__n` as globals in every component template |

**The build**

| Concept | What it is |
| --- | --- |
| `build_shell` | `bench build` writes the manifest, installs packages if needed, builds once, and swaps the output in |
| One vite config | One build for all apps, served at `/assets/frappe/frontend/` |
| Entry chunk rule (`entryChunk`) | Every module the cold load runs goes in one `shell` chunk beside the entry, so a lazy chunk that shares one never splits it out. The import map's names load by `import()`, so they do not count as cold-load modules |
| Aliases (`@/`, `@shell`, `vue`) | `@/` is private to the framework; `@shell` gives app files the desk names. `vue` is Vue's runtime build for every importer, a CommonJS package too, so no template compiles in the browser |
| [Manifest](./CONTEXT.md#manifest) | The part the bundler needs moves here from `frappe/shell/` |
| Shared packages ([singletons](./CONTEXT.md#singleton)) | `enforce_singletons` checks them at build time |
| `desk.package.json` | An app's declared frontend packages, merged into one `package.json` and lockfile |
| [Contribution layout](./CONTEXT.md#kind) and discovery | The file paths that count as contributions, and the walk that finds them |
| Replacement pages (`pages.json`) | A doctype's `pages.json` replaces its standard list or record page |
| Page clash warnings | Warns when a page slug equals a doctype or module slug |
| Shared `node_modules` | An app's bare imports resolve from the framework's `node_modules`, only if the app declares them |
| Import map | Points each name on the import list at a built file |
| `classes.json` | Every CSS class the build defines |
| Tailwind presets and content | Each app's theme preset, and the folders Tailwind reads |
| Template plugin | Calls the template compiler for each `.js` and `.ts` app file that holds the word `template`. Stops `bench build` on a template error, and returns a source map |
| Layer file (`frontend/architecture/layers.json`) | Each layer's paths and the layers it may use, and each of today's breaks with the ticket that removes it |
| `/desk-architecture` | In developer mode, a System Manager's page of the layers, the flows and every import that breaks the layer file, built from the working tree on each request |

**The template compiler**

| Concept | What it is |
| --- | --- |
| Compile module (`compileScript`, `cacheKeyParts`, `TEMPLATE_KEY`) | Finds each unquoted `template:` key and checks its names. Then it compiles the template with `@vue/compiler-dom` from `frontend/node_modules` and keeps every line number. Both tiers call it, so they give the same output and errors |
| Names file | The names a template can use with no `components:` entry: `RouterLink`, `RouterView`, Vue's built-in components, `__` and `__n`. Part of the cache key |

## Ways to change the desk

Every way an app, a site admin or a user changes the desk, with the layer that holds it.
"Same job as" names another way that does the same job.

| Way | Who | Layer | How it is registered | What it changes | Same job as | Note |
| --- | --- | --- | --- | --- | --- | --- |
| record.js file script | App | 9 | A file in the app's frontend folder, found by the build | Handlers on a doctype's record page | Stored script |  |
| Stored script | Site | 9 | A Client Script row with view = Record | Handlers on a doctype's record page | record.js file script |  |
| list.js list file | App | 9 | A file in the app's frontend folder | A doctype's list, such as extra columns |  |  |
| acts.js acts file | App | 9 | `<module>/frontend/acts.js`, found by the build | Global acts on the shell surface, for the palette, keys and `page.run` |  |  |
| item.js item file | App | 9 | A file in the app's frontend folder | How one kind of navigation item draws | navigation_item_resolvers hook | Winner rule differs today: first app wins the renderer, last app wins the visibility hook |
| App page | App | 8 | A page file the build registers | Adds a page under the app's prefix |  |  |
| Replacement page (pages.json) | App | 8 | pages.json beside a doctype | Replaces the standard list or record page for a doctype |  |  |
| @shell import alias | App | build | Vite alias | Desk names an app file may import | import_map hook | Two import lists; the target has one |
| import_map hook | App | build | hooks.py | Names a stored script may import | @shell import alias | Two import lists; the target has one |
| desk.package.json | App | build | A file in the app | The app's frontend packages |  |  |
| Tailwind preset | App | build | A preset file in the app | The app's theme |  |  |
| app_prefix hook | App | 2 | hooks.py | The address prefix the app claims |  |  |
| app_modular hook | App | 2 | hooks.py | Whether record addresses include the module |  |  |
| app_permission hook | App | 2 | hooks.py | Who may enter the app's prefix |  |  |
| app_boot hook | App | 2 | hooks.py | Extra keys in the boot payload |  |  |
| add_to_apps_screen hook | App | 2 | hooks.py | The app's tile on /apps |  |  |
| navigation_item_resolvers hook | App | 2 | hooks.py | Who can see the app's own item type | item.js item file |  |
| Cross-app rail rows (app:key) | App | 2 | Navigation rows shipped by another app | Adds rows to another app's rail |  |  |
| Settings panes and blocks | App | 1 | A Settings Dialog record shipped with the app; `extends` adds blocks to a host's panes | The app's panes in the settings dialog |  |  |
| Settings component file | App | 9 | A `.vue` file in the app's `frontend/settings/` folder | One component block in a settings pane |  |  |
| Base rail and sidebars | App | 1 | Rail and Sidebar records shipped with the app | The app's navigation |  |  |
| Site rail and sidebar copy | Site | 1 | Rail and Sidebar site layer, or the customize dialog | Navigation for every user on the site |  |  |
| Form Layout | Site | 1 | A Form Layout row | Details, Side Panel, Quick Entry or New Record layout, and inline fields in the two create layouts | Stored script | A field can be hidden three ways: the layout, a script, or the DocType |
| Doctype View (site) | Site | 1 | The list's column and sort panels, saved for the site | Default columns, sort and quick filters |  |  |
| DocType and Customize Form | Site | 1 | DocType or Property Setter rows | Fields, labels, hidden, read-only |  |  |
| Doctype View (user) | User | 1 | The list's column and sort panels | The user's own columns, sort and quick filters |  |  |
| Arrangement (user) | User | 2 | The customize sidebar dialog | The user's order of rail and sidebar items |  |  |
| Index layer (user) | User | 2 | Arrange apps in the avatar menu, or Hide in a tile's menu | The user's order and hidden tiles on /apps |  |  |
| Per-user rail and sidebar | User | 1 | Rail and Sidebar user layer | Rows the user hides or adds |  |  |

## The flows

Each flow is written as it will be after the accepted cuts. Each step names its layer, its
permission check, and its cache with the cache key. A check marked **browser** only
changes what is shown; the server makes the same check again. No flow has a permission
check that exists only in the browser.

Each flow has a budget: the measures it must stay under. The guardrails ticket sets the
numbers. Every flow is also counted in files per flow and in timing guards.

### Boot: open `/apps/<prefix>` to the painted shell

| # | Step | Layer | Permission check | Cache and key |
| --- | --- | --- | --- | --- |
| 1 | The website router finds the shell page. It maps the prefix to an app and returns the built `index.html` | 2 | App permission, `guard_prefix` | Built page in process memory, by file path. Prefix map in the site cache |
| 2 | An inline script sets the light or dark theme before the first paint | `index.html` | None | `localStorage` `theme` |
| 3 | `main.ts` asks for boot and waits. A refusal shows the "no permission" page state | `main.ts`, 5, 3 | None in the browser | None |
| 4 | The server builds boot: core keys, session, `metadata_version`, prefix map, and the rail and sidebars filtered for the user | 2, 1 | App permission; each navigation row filtered by readable doctypes, modules and pages. On the index, each favourite filtered by its record's read permission and its app's permission, each recent visit by its app's permission and its doctype's or record's read permission, the setup nudge to System Managers, and what's new to System Managers and Workspace Managers | Session in Redis by session id; `metadata_version` and prefix map in the site cache; navigation not cached. On the index, the user layer in `_user_settings` by `/apps` and user |
| 5 | Translations and the icon sprite start, not awaited. `main.ts` registers the Create dialog | 5, 6 | None | HTTP cache, 1 year, by language and translation version. The sprite is a static file |
| 6 | The address table loads, awaited | 5, 3, 2 | The user may enter at least one app | One server cache key, checked against `metadata_version`. HTTP cache, 1 year, by `metadata_version` |
| 7 | `main.ts` registers the standard pages. Contributions register item kinds, app pages, replacements and handlers. The record page registers its icon and prop hooks | 5, 7, 8 | None | Browser memory, by item kind, by address kind and doctype, by doctype |
| 8 | The router is built from boot, addresses and page registrations. Recents start listening to it, so the first page is kept too | 6 | None. The router checks only that an address names a known doctype | Browser memory; recents in `localStorage`, per user |
| 9 | The socket opens and is handed to `ui/`. The desk hands `ui/` its session. Each cache of site data listens for `doctype_update` itself | 6, 3 | Realtime server: the user room; the site room for System Users only; each document room by read permission | Session store in browser memory |
| 10 | The shell draws the rail and sidebar, before any page code arrives. Each row is drawn by its kind's renderer | 6, 5 | **Browser**: none; the rows were filtered in step 4 | Per-user browser memory: open sections, collapsed sidebar. Sidebar memory per tab, by address and user |
| 11 | The router sends the bare address to its landing, or shows the nothing to open state. On the index, the index page draws boot's apps, favourites, recent visits and notices with no request | 6, 5, 8 | **Browser**: none; the rows and the index's apps, favourites and recent visits were filtered in step 4 | None |
| 12 | At idle after the first paint, the shell imports each active app's `acts.js` and joins its acts to the shell surface | 6, 5 | **Browser**: each act's `right`, at dispatch. The server checks every call an act makes | Browser module map; the files are code, versioned by the build |

**Budget:** first paint time; boot size; `get_boot` time on the server; no request sent
twice; layout shift; the shell drawn before the page's code arrives; a change on screen
soon after any click. For Home: on a cold load, time until usable, request count and JS
size; on a return visit, skeleton frames and time until usable.

### Open a list: sidebar click to rows painted

| # | Step | Layer | Permission check | Cache and key |
| --- | --- | --- | --- | --- |
| 1 | A sidebar row's link, built with `routeFor`, is clicked | 6, 5 | None | None |
| 2 | The router checks the slug against the address table | 6 | None: an address check, not a permission check | Browser memory |
| 3 | The address and the frame change at once. The page shows its skeleton, and the registered page's code starts loading once that frame has painted. The shell picks the sidebar for the new address | 6 | None | Loaded pages in browser memory. Sidebar memory per tab, by address and user |
| 4 | The list page asks for the doctype's meta. Roles come from the session | 7, 3 | Any signed-in user | Browser memory, by doctype; marked stale on `doctype_update` |
| 5 | The list loads its saved settings (the site row and the user's row) and works out columns, sort and quick filters | 7, 3 | Read on the doctype; System Manager for the site row. **Browser**: columns on fields the user cannot read are dropped | Browser memory, by doctype; marked stale on `doctype_update` |
| 6 | The rows are read, with the count on the first page | 7, 3, 1 | Doctype read, row rules and field permissions in the query | Data cache, by doctype and query. Rows memory, by doctype. Page size and scroll in the history entry |
| 7 | The rows paint and the scroll is restored. The column and sort panels load only when opened. An empty or failed read shows a page state | 4, 7, 8 | None | As step 6 |

**Budget:** on a cold load, time until usable, request count, JS size. On a return visit,
skeleton frames, time until usable, re-reads.

### Open a record: row click to the record page painted

| # | Step | Layer | Permission check | Cache and key |
| --- | --- | --- | --- | --- |
| 1 | The row link goes through the same router steps as the list. The frame changes at once | 6 | None | Loaded pages in browser memory |
| 2 | The record page starts a visit: skeletons, the last form tab, and the record's room | 8, 3 | Realtime server: read permission on the room | Per-user browser memory: form tab by doctype |
| 3 | In parallel, the script loader starts (see the last flow) and the two form layouts load | 7, 3 | Layouts: read on the doctype | Scripts by doctype, marked stale on `client_script_changed`; layouts by doctype and type, marked stale on `doctype_update` |
| 4a | Return visit: if memory holds every part the visit needs, the page paints from memory at once, then re-reads. Background reads land in one repaint | 8, 3 | None before the paint. The re-read carries the server check. A refusal shows the "no permission" page state | Data cache, by doctype and name |
| 4b | First visit: the activity read starts beside the record read | 8, 3 | Read permission on the record | Activity store, by record |
| 5 | The record is read with its parts and meta, and goes into the data cache | 8, 3, 1 | Read permission and field-level read rules | Data cache, by doctype and name; meta by doctype |
| 6 | The engine builds `page` with its rights, roles and field access | 7 | **Browser**: field access by permission level. The server checks it again on save and on every read | Handlers by doctype |
| 7 | Built-in actions are offered by right: email, print, tags, attach, delete, share, assign | 8 | **Browser**, by right. The server checks each action | None |
| 8 | First paint: the page waits for layouts, feed and scripts, runs one replay, paints, then runs held acts | 8, 7 | None | None |
| 9 | Header, body, tabs, form, panel and feed draw. Saved comments show as cleaned HTML; the editor loads only to write. On a return, the reader's view comes back before the first frame | 8, 4 | None beyond steps 6 and 7 | Per-user browser memory: open sections, body columns, dock height. The record view: in the history entry, and by doctype and name while the record's complete cache entry stays |

**Budget:** on a cold load, time until usable, request count, JS size, paints. On a return
visit, skeleton frames, time until usable, re-reads, paints.

A record shown from memory after its access was removed is accepted. The same user saw
that copy in the same tab, and the page shows "no permission" once the server replies.

### Create: the Create button to the saved record

| # | Step | Layer | Permission check | Cache and key |
| --- | --- | --- | --- | --- |
| 1 | The list and a Link field show Create when the person may create the doctype's records. `page.create()` opens Create with no check in the browser | 8, 7, 5, 4 | **Browser**: the create right, from the meta, the session roles and read-only mode | Meta by doctype, as in "Open a list" |
| 2 | `openCreate` puts a request on the shell's stack. The Create dialog that `main.ts` registered draws it | 6, 8 | None | Open requests in browser memory. A route change closes them |
| 3 | The dialog reads the Quick Entry layout and the new document's defaults (`get_new_doc`) in parallel | 8, 7, 5, 3, 1 | Layout: create or read on the doctype. Defaults: create on the doctype | Layouts by doctype and type, marked stale on `doctype_update`. Defaults not cached |
| 4 | With no Quick Entry row, the server sends the Quick Entry fields. The `dialog` flag is off only with no row and a doctype that gets no dialog: no `quick_entry` flag, no field to show, or a mandatory table. Then the dialog never shows: the request resolves `null`, and the router opens `/<doctype>/new` with the values in the query | 1, 8, 6 | As step 3 | As step 3 |
| 5a | Dialog: the form shows the layout, a name field for a doctype named by prompt, the defaults and the caller's values. Save, Ctrl/Cmd+Enter or Ctrl/Cmd+S inserts | 8, 7, 5, 4 | **Browser**: required fields | None |
| 5b | Full page: the new record page reads the meta, the New Record layout, the stored scripts and the defaults. It reads the Quick Entry layout too when the address carries values. Its first save inserts | 8, 7, 5, 3 | As step 3. **Browser**: the create right, else the "no permission" page state | Layouts by doctype and type. Scripts as in the last flow |
| 6 | The insert sends a typed name as `__newname`, never `name` | 5, 3, 1 | Create permission, the naming rule, field permission levels | None |
| 7 | Dialog: the request resolves with the saved record after the close renders. The list re-reads its rows and shows a toast that links to the record. A Link field takes the name, and the title when the doctype shows titles in links. Full page: `onSaved` replaces the address with the saved record's | 8, 7, 6, 4, 3 | Read permission on the re-read | Data cache, by doctype and query |

The layer file counts this flow's files from the new record page. The dialog loads on
demand, so the count leaves it out.

**Budget:** on a cold load of `/<doctype>/new`, time until usable, request count, JS size.
For the dialog, the requests on its first open. The numbers are an open question:
[Guardrails: a page-JS and API-call baseline for the new record page](https://github.com/frappe/frappe/issues/45059).

### Save: edit a field and save, to the saved state shown

| # | Step | Layer | Permission check | Cache and key |
| --- | --- | --- | --- | --- |
| 1 | A field changes. `FormLayout` writes the value into the draft and reports the change | 4 | **Browser**: a field the user cannot write is read-only | None |
| 2 | The engine's commit channel drops repeats and runs the field's handlers | 7, 9 | None | None |
| 3 | Save, from the button or from Ctrl+S, takes one path: one saving state, and the same paint hold. The engine clears the field errors, runs owed changes, `beforeSave`, the mandatory check, the page's save, then `afterSave`. A failed mandatory check marks each empty field and sends nothing | 8, 7, 9 | **Browser**: required fields. Save is offered to every reader; the server decides | None |
| 4 | The page sends the draft with `modified`, one request at a time. It refuses if the visit has changed | 8, 3 | None | None |
| 5 | The server saves: write check, timestamp check, higher permission levels reset, a version row, and `doc_update` after the commit. The reply has field-level read rules applied | 1 | Write permission; field permission levels; field-level read on the reply | None |
| 6 | The reply goes into the data cache. On a timestamp conflict, the page re-reads the record and asks the reader what to do. On compile errors, the page lists them in a dialog and marks them in the Code field. On any other refusal, the page marks each field the reply names and shows the message. After a failed save, the reader lands on the first marked field | 3, 8, 7 | The re-read checks read permission | Data cache, by doctype and name, in request order |
| 7 | The page shows the saved state with a visible confirmation, re-reads the side parts, and replays surfaces and handlers | 8, 7, 3 | Read permission on the re-read | Data cache |
| 8 | The record room's listener hears `doc_update`, and the feed re-reads its newest page | 4, 3 | Room and feed read permission | Activity store |

**Budget:** time until the saved state shows; request count; a visible confirmation.

### Load a stored script onto a record page

| # | Step | Layer | Permission check | Cache and key |
| --- | --- | --- | --- | --- |
| 1 | A record visit asks the script loader for its doctype's scripts, beside the record read. The first visit to a doctype registers its file scripts, before any stored script | 8, 7 | None | One entry per doctype; the latest load wins |
| 2 | The loader fetches the enabled stored scripts for the Record view | 7, 3 | None | Not HTTP-cached |
| 3 | The server checks read on the doctype, reads enabled rows in run order, drops rows of disabled modules, and says whether the user may write scripts. For a script that holds `template:`, it sends the compiled copy. A cache miss compiles all such scripts of the doctype in one `node` call. A script that fails to compile goes out with its error and no code | 1 | Read permission on the doctype; write permission on `Client Script` for the answer | Disabled modules, per request. Compiled copies in Redis, keyed by source hash, compiler version, build, options, compile script version and names file |
| 4 | The loader keeps the write answer. Only a script writer sees failure toasts and the editor entry | 7 | **Browser**. The server checks `Client Script` write on save | Browser memory |
| 5 | Each script loads as a module; its bare imports resolve through the import list. Its handlers register under its name, beside the app's file scripts. A failing script, or one sent with a compile error, is skipped and reported | 7, 9 | None | Browser module map |
| 6 | The engine holds the first paint until the scripts are in or 500 ms pass, then replays | 7 | A script's own checks on `page.roles` or `page.perms` only change what is shown | None |
| 7 | A saved, reordered or deleted script sends `client_script_changed` to the site room. The loader marks its entry stale, and an open record page with no unsaved edits re-runs its scripts. The next load keeps the old scripts until the new ones have compiled | 1, 7, 8 | The site room admits System Users only | The doctype's entry is marked stale |

**Budget:** the first paint waits at most 500 ms for stored scripts. A cache miss on compiled scripts adds one `node` call, about 40 to 60 ms.

## Guardrails

These rules keep the code to what this file describes. A rule that a tool can check has a CI check.
A rule that no tool checks well is a fixed question in every review. Each map close runs
a review of the whole desk. The [guardrails ruling](https://github.com/frappe/frappe/issues/43433)
made each choice here.

**A check compares against a baseline.** The baseline is today's count, kept in a file. A
PR may lower a count. A PR that raises a count fails, unless the same PR edits the
baseline, so the reviewer sees the raise in the diff. A PR that lands a cut lowers the
baseline in the same PR.

**The CI checks**

| Rule | The check fails when | Where it runs | Baseline |
| --- | --- | --- | --- |
| A layer uses only the layers it may use, and `ui/` uses no desk code | An import goes to a layer that the layer file does not allow. Every file in `ui/src` and `ui/island` is checked, also one the desk does not import | Frontend workflow, step "Check the desk structure": `node frontend/architecture/diagram.mjs --flows` | `knownBreaks` in `frontend/architecture/layers.json`, each with the ticket that removes it |
| No new group of folders imports each other | A new group appears, or a known group grows or joins another | Frontend workflow, the same step | `knownLoops` in `layers.json`: 9 groups |
| A new concept needs a ruling | A name imported or re-exported across a folder boundary is not in the concept table of the layer that defines it. A `ui/` name that is not public fails as `NOT PUBLIC`, because it gets no row | Frontend workflow, the same step | `knownUnlisted` in `layers.json`: today's gaps. The step prints how many are internal `ui/` names |
| Framework code outside `frappe/shell/` does not use the desk server | Code outside `frappe/shell/` imports `frappe.shell` or names it in a dotted path. Test files are skipped, and a `hooks.py` callback is not a use | Python tests, `frappe/tests/test_desk_server_layer.py` | The `knownBreaks` from outside `frappe/shell/` into it: `frappe/utils/data.py`, `frappe/bundler.py` and `frappe/website/page_renderers/shell_page.py` |
| Every test file runs | A test file under `frontend/` or `ui/` matches no vitest pattern | Frontend workflow, `yarn test:files` | None |
| A page's JS does not grow past its baseline | A page's JS is more than 5 KB gzip above its baseline | Frontend workflow, `yarn test:page-js` | `frontend/speed-budgets.json` |
| A page does not send more API calls than its baseline | A cold load of home, list, record or a new record, a save, or the first or a later open of the list's Create dialog sends more API calls than its baseline. There is no tolerance | UI workflow, the Playwright spec `playwright/tests/desk_v2_api_calls.spec.js` | `frontend/speed-budgets.json` |

CI also prints the files that each flow's entry file reaches, but does not fail on the
count. A fail on file count pushes code into fewer, larger files. The entry files are
`flowEntries` in `layers.json`. CI does not check timings, because they change from one
CI run to the next. There is no CI limit on the count of concepts in a layer, because the
concept tables are closed lists.

**The budgets.** The baselines move down to these targets. All times are at a 4x slower
CPU.

| Page or flow | Target |
| --- | --- |
| Every page | First paint 300 ms or less. Boot 15 KB or less. Layout shift 0.1 or less. No call sent twice |
| Home, cold | 400 ms, 4 calls, 300 KB JS |
| List, cold | 600 ms, 7 calls, 320 KB JS |
| Record, cold | 700 ms, 9 calls, 460 KB JS |
| New record, cold | 9 calls, 460 KB JS |
| Return visit to any page | No skeleton frame, 50 ms or less |
| Save | The call count measured when the check was added. No time target until the save shows a confirmation |
| Create dialog, open | The call count measured when the check was added, for the first open and for a later one |

When a page meets its budget, the simpler code wins over more speed.

**The review questions.** No tool checks these rules well. Every review brief asks:

1. Does this PR add a second way to do a job that one mechanism already does?
2. Does it add a timing guard: a counter, a debounce, a gate or a fetch-once flag?
3. Does it add a DocType, a route, a store or a lifecycle event that is not in the concept tables?
4. Can this be done with fewer concepts or less code?

**The cost line.** Every build PR's description states six fields. A field that does not
apply says "none". The ticket's resolution links to it. The review subagent checks the
fields. CI does not.

1. Concepts added and removed, by name from the concept tables.
2. Pairs of mechanisms that do the same job, added or removed.
3. The change in files per flow, for each flow in `flowEntries` in the layer file.
4. The change in API calls and JS bytes for each page the PR touches.
5. The permission check for each new way in to the server or the data.
6. The cache key and the clear rule for each new cache.

**The whole-desk review at each map close.** The session that closes a map starts a fresh
subagent and gives it none of the session's reasoning. The subagent reads this file, the
layer file, the output of the checks against the baselines, and the git diff for the life
of the map. It runs the [return-visit walk](./walks/README.md) at a 4x slower CPU for
timings, return visits, layout shift and save time. Today the walk counts skeletons and
redraws on return visits only. The CPU setting, timings, layout shift and save time are
not built yet. It counts files per flow and concepts
per layer. It posts one comment on the root map, [Desk v2](https://github.com/frappe/frappe/issues/42061):
the counts before and after, new concepts, new pairs that do one job, and each place where
the code left this file. The user rules on each finding. Each accepted finding becomes a
ticket on the map that owns its area. A map does not close until the comment is posted.

## Where the code is not there yet

Each row is a place where today's code breaks this file. The PR that closes a row
removes it. The owner is the map that builds the change, as the target architecture
ruled. The hand-off ticket that files each cut on its map can change an owner.

| Owner | What it covers |
| --- | --- |
| One page model ([#43265](https://github.com/frappe/frappe/issues/43265)) | The record page's runtime: the engine, `Record.vue`, the script loader |
| Return visits ([#43276](https://github.com/frappe/frappe/issues/43276)) | Painting a record or list from memory on a return visit |
| Activity column ([#42758](https://github.com/frappe/frappe/issues/42758)) | The activity feed, the composer and its writers |
| Build and publishing ([#43085](https://github.com/frappe/frappe/issues/43085)) | The build, `main.ts`, contributions and the import list |
| @framework/ui ([#42660](https://github.com/frappe/frappe/issues/42660)) | Everything in `ui/` |
| New map | The shell, the list, the router and the server routes. Not created yet |

**Layer breaks and moves**

| Today | Target | Owner |
| --- | --- | --- |
| `get_url_to_form` in `frappe/utils/data.py` imports `frappe/shell/links.py`, and there are two record address builders | One record address builder in layer 1 | New map for the shell, list, router and server routes |
| `frappe/bundler.py` imports `frappe/shell/manifest.py` | The manifest code the bundler needs moves into the build | Build and publishing |
| The shell page renderer is in `frappe/website/page_renderers/` and imports `frappe/shell/` | It moves into `frappe/shell/`, found through the `page_renderer` hook | New map |
| `routeFor` is in `router/` and the item contract is in `navigation/types.ts` | Both move to layer 5 | New map |
| `contributions/registry.ts` imports `@/recordPage` to hand over record handlers | The registry no longer imports the engine | Build and publishing |
| `shell/ComposerWindow.vue` imports the writers from `pages/record/composer/`; `shell/composer.ts` imports types from `@/recordPage` | The record page registers its writers | Activity column |
| `shell/doctypeUpdates.ts` imports the layout and list settings caches | Each cache marks itself stale on `doctype_update` | Build and publishing |
| `main.ts` sets the record page's icon and prop hooks | The record page sets them when it registers | Build and publishing |
| `useSession`, `useDoctypeMeta`, `useDocPermissions` and `useUserRoles` sit in the component layer | They move to `ui` data | @framework/ui |
| Two import lists: the `import_map` hook for stored scripts, `@shell` for app files | One import list | Build and publishing |
| `useDoctypeMeta` imports a type from `components/FormLayout` | `ui` data uses nothing in `ui` components | @framework/ui |
| `ui/src/api` and `ui/src/cache` import each other | The cache does not import the request code | @framework/ui |

**Concepts that change**

| Today | Target | Owner |
| --- | --- | --- |
| 11 hand-written "latest reply" counters | One "latest reply wins" helper | New map |
| Two listeners on each record room | One | Activity column |
| Separate comment and email writer pipelines | One | Activity column |
| Two server cache keys for doctype owners and the address table | One | New map |
| First app wins for item kinds; last app wins for replacements | Last app wins everywhere | Build and publishing |
| The session fetched twice | The desk passes it | @framework/ui |
| Record page words in four `ui/` files, and the commit channel in `ui/` | Both in `frontend/` | @framework/ui |
| The editor loads to show saved comments | Cleaned HTML; the editor loads to write | Activity column |
| The list's column and sort panels load with the list | They load when opened | New map |

**Where `ui/` does not stand on its own yet.** The @framework/ui map owns each row.

| Today | Target |
| --- | --- |
| The cache keeps a record only when all nine record page parts were read | The cache keeps any read; the desk decides what a return visit needs |
| Number and currency formats read a session only the desk provides | `ui/` loads the session itself when none is passed |
| A form needs the desk's save channel | A form works without it |
| The condition builder reads desk v1's `__` | It uses `ui/`'s own translate function |
| The phone field reads a country list from the Python package | The list ships inside `ui/` |
| The CSRF token is read from a global | `ui/` gets it itself, or takes it as a documented input |
| Upload limits come only from desk boot | They have a default and can be passed in |
| The socket is found by guessing four places | It is a documented input, with a warning when it is missing |
| Translations need the boot version | They work without it |
| The activity feed exports the desk's first-paint functions | Those move to `frontend/` |
| Field access by permission level is set only by the desk | `ui/` works it out itself |
| The invite redirect defaults to `/app` | The app passes the address |
| `ui/` has no test setup of its own | It has one |
| `reka-ui` is used but not declared | It is declared |
| About ten comments use record page words | They do not |

Kept now that `onOpen` is built: the late part of an async `onRefresh` lands as a later
paint, and an act from `onRefresh` lands in the first replay and is dropped in the replay
after the background reads. `onOpen` is where a one-time act belongs.
