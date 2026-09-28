# Desk v2 architecture

This file is the map of desk v2: the layers, the concepts each layer keeps, and the five
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
  code adds the name here.
- **A removed concept leaves in the PR that removes it.** So does a row in the gap list.
- **A new layer, or a new "may use" edge between layers, needs a ruling.**
- **Line count is never a measure here.** Simple means few concepts, one way to do each
  job, few files per flow, and no layer that uses a layer above it.

## The layers

There are nine layers. **Each layer may use only the layers below it.** "Use" means a
static import or a direct call. A lower layer may run a function that a higher layer
registered with it, such as a script's handler or a page's save. That is a callback, not
a break: the lower layer owns the contract, and the higher layer fills it.

Code in the browser reaches the server only through HTTP, under `/api/v2`.

| # | Layer | Holds | Where | May use |
| --- | --- | --- | --- | --- |
| 9 | Customization | Code an app or a site adds: file scripts, stored scripts, list and item files | App folders; `Client Script` rows | Only the [import list](#9-customization), and the `page` object it is handed |
| 8 | Pages | Home, module, list page, record page and its parts; pages an app contributes | `frontend/src/pages/`; app `frontend/pages/` and replacement pages | 1 to 7 |
| 7 | Page engines | The record page engine and its `page` object; the list engine; the script loader | `frontend/src/recordPage/`, `frontend/src/list/` | 1 to 6 |
| 6 | Shell | Rail, sidebar, navigation, router, page frame, page states, composer window, socket | `frontend/src/shell/`, `navigation/`, `router/` | 1 to 5 |
| 5 | Desk services and registry | Boot data, addresses and `routeFor`, translations, icons, arrangement, browser memory; the registry of everything an app adds | `frontend/src/` root modules, `icons/`, `contributions/` | 1 to 4 |
| 4 | `ui` components | Fields, forms, lists, filters, the activity feed, the composer, upload | `ui/src/components/`, `ui/src/experimental/`, `ui/island/`, the other composables | 3, and 1 through it |
| 3 | `ui` data | Requests, the data cache, the socket rooms, the session, meta, permissions | `ui/src/api/`, `ui/src/cache/`, `ui/src/socket.ts`, `ui/src/utils/`, the four data composables | 1 |
| 2 | Desk server | The shell page, boot, the address table, navigation, arrangement, app prefixes | `frappe/shell/` | 1 |
| 1 | Framework server | Documents, permissions, REST API v2, the desk v2 DocTypes, the record address | `frappe/` outside `frappe/shell/` | nothing above it |

The four data composables are `useSession`, `useDoctypeMeta`, `useDocPermissions` and
`useUserRoles`.

Two things sit outside the nine layers:

- **`frontend/src/main.ts` sits above all of them.** It wires every layer at start-up,
  and nothing imports it. It is the only file that may use every layer.
- **The build sits beside them.** It reads app folders and writes the registry file and
  the import map. The running desk never imports it. The build is `frontend/plugin/`,
  `frontend/vite.config.js`, `frappe/bundler.py`, the manifest code the bundler needs,
  and `ui/vite/`.

### `ui/` stands on its own

`ui/` (the `@framework/ui` package) is a library for every Frappe app, not a part of the
desk. Layers 3 and 4 may use only the framework server through REST API v2, their own npm
dependencies, and their own files. They never use `frappe/shell/`, `frontend/`, desk boot
data, or record page words.

- **The desk passes in what only the desk has**: the session, the CSRF token, the socket,
  upload limits, and the invite address. `ui/` works, with a sensible default, when an
  app passes none of them.
- **Judge `ui/` by what it exports**, not by what the desk imports. No app uses `ui/`
  yet, but apps will. "No app uses it today" is never a reason to cut or change something
  in `ui/`.
- **The public surface is the root index and the named subpaths** in `ui/package.json`.
  The `"./*"` entry stays for now, so any file can still be imported. A deep import
  carries no promise.

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

Rows marked *new* do not exist in code yet. An accepted cut or a `ui/` change adds them.

### 1. Framework server

| Concept | What it is |
| --- | --- |
| `Rail` | The app icons down the left edge, per app, with site and per-user copies |
| `Sidebar` (`navigation_items` table) | A sidebar per module or doctype. Desk v2 reads `navigation_items`; desk v1 reads `items` |
| `Navigation Item` | One row in a rail or sidebar: key, parent, type, target, label, icon, anchors |
| `Navigation Item Type` | A kind of navigation row, and the rule for who can see it |
| `Doctype View` | Saved list settings (columns, sort, quick filters), per person or per site |
| `Form Layout` | A stored layout for a doctype's Details, Side Panel or Quick Entry, with an optional condition |
| `Client Script` with `view = Record` | A stored script that the desk v2 record page runs |
| Client Script class check | On save, warns about CSS classes the build does not define. Reads the build's `classes.json` |
| `code_only_modules` hook | Modules that hold only code. Their navigation goes to named heir modules |
| Layer resolution (`frappe.desk.layers`) | Merges base, site and user copies of a list and places items by anchors |
| Record address | The one address of a record under `/apps/<prefix>/`. `get_url_to_form`, emails and the desk all use it. *New: moves here from `frappe/shell/`* |
| Realtime events | `doc_update`, `docinfo_update`, `doctype_update`, `list_update`, `client_script_changed` |
| Doctype View routes | Get, save and reset a list's saved settings |
| `get_form_layouts` | A doctype's stored Form Layouts of one type |
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
| `app_prefix` hook | The address prefix an app claims, for example `desk` |
| `app_modular` hook | Whether an app's record addresses include the module |
| Prefix registry | Map of prefix to app, cached per site, cleared on app install |
| Shell path helpers | Split an `/apps/...` path into prefix and rest, and find its app |
| `app_permission` hook | Who may enter an app's prefix. Missing means "is a System User" |
| `guard_prefix` | Sends a guest to login, or refuses a user without app permission |
| Boot payload | The keys every page gets at start, plus the app's own keys |
| `app_boot` hook | An app adds its own boot keys. A failing one is dropped and logged |
| `add_to_apps_screen` hook | Title and logo of an app tile on `/apps` |
| Boot key limit | Logs any boot key over 100 KB |
| `metadata_version` | Boot key that changes when doctypes change |
| Address table | Each doctype and module mapped to its slug and owning app. One server cache key |
| `slug` | `Sales Order` to `sales-order` |
| Address clash guard | Refuses a DocType or Module name whose slug clashes with a page |
| Reserved route guard | Refuses any website route that starts with `apps` |
| Prefix check on install | Refuses an app whose prefix is taken or malformed |
| Navigation resolution | Builds an app's rail and sidebars from base, site and user layers, filtered for the user |
| Cross-app extensions (`app:key`) | Another app's rail rows, merged in with namespaced keys |
| Visibility rules (`NavigationContext`) | Decides per row whether the user may see it |
| `navigation_item_resolvers` hook | An app supplies the visibility rule for its own item type |
| Arrangement | Stores only the difference between a user's or site's order and the layer below |
| `get_boot` | The boot payload for a path |
| `get_addresses` | The address table, HTTP-cached on `metadata_version` |
| `get_contents` | The doctypes, reports and pages of an app or module that the user can read |
| Arrangement routes | Get, save or reset a rail or sidebar order |

### 3. `ui` data

The list is what `ui/` exports from its root index and from `@framework/ui/api`.

| Concept | What it is |
| --- | --- |
| Response envelope (`Envelope`, `ApiError`, `isApiError`, `readEnvelope`, `TIMESTAMP_MISMATCH`) | Every `/api/v2` reply is `{ data }`; every failure is one error class |
| Request transport (`request`, `apiUrl`, `requestHeaders`) | The one fetch wrapper for `/api/v2`. Takes the CSRF token as a documented input or finds it itself |
| Document calls (`getDocument`, `listDocuments`, `countDocuments`, `searchDocuments`, `createDocument`, `updateDocument`, `deleteDocument`, `copyDocument`) | Read and write one record or a list |
| Method calls (`runMethod`, `runDocumentMethod`) | Call a whitelisted method, or a method on one document |
| `getMeta` | Fetch a doctype's meta |
| Record parts (`getDocumentPart`, `addPart`, `removePart`, `updatePart`) | Read or change one named part of a record |
| Collaboration calls (`addAssignment`, `addShare`, `addTag`, `addFavourite`, `addFollow`, and each `remove`) | One pair of calls per side panel feature |
| Comment calls (`addComment`, `updateComment`, `removeComment`) | Post, edit and delete a comment |
| File calls (`uploadFile`, `attachFile`, `removeAttachment`, `downloadFile`) | Upload in chunks and attach to a record |
| Session calls (`getSession`, `logout`, `getTranslations`) | The signed-in user, sign-out, and translations |
| Data cache (`readCachedDocument`, `readCachedList`, `readCachedRows`, `clearDataCache`, `listCacheKey`, `DocumentEntry`, `ListEntry`) | The one in-memory store of records and list queries. Every reply goes into it, in the order the requests were sent. It keeps any read |
| Session store (`useSession`, `setSession`, `provideSession`, `currentSession`, `SessionKey`) | One shared session. The desk passes its own; `ui/` fetches one only when none is passed |
| Doctype meta store (`useDoctypeMeta`, `DoctypeMeta`) | Fetches and holds each doctype's meta. Clears itself on `doctype_update` |
| Scoped registry (`setScoped`) | Overrides a map entry for one Vue scope |
| Socket input | *New shape.* The app hands `ui/` its socket, and `ui/` joins record rooms on it. `ui/` warns when there is none |
| Translate function | *New.* `ui/`'s own `__`, which works without the desk's boot version |

The desk also imports about 20 files by path, for example `useDocPermissions`,
`useUserRoles`, `socket.ts`, tab identity and child row identity. They are not on these
lists and carry no promise. The @framework/ui map decides the public surface.

### 4. `ui` components

The list is the rest of the root index and the named subpaths. Each row is a subpath or a
component group, with its main names.

| Concept | What it is |
| --- | --- |
| `FormLayout` (`@framework/ui/FormLayout`: `FormLayout`, `FormLayoutSchema`, `Tab`, `Section`, `Column`, `FieldNode`) | Draws a form from a tabs, sections, columns and fields tree. Works out field access itself |
| Layout building (`buildLayoutFromMeta`, `compose`, `Decorator`, `fieldsToLayout`, `resolveLayout`, `evaluateDependsOn`) | Turns meta fields into a layout tree, and applies depends-on, hidden and overrides for one document |
| Child rows (`useChildRowModel`, `newRowValues`) | The rows of a child table field, and a new row's default values |
| Value formatting (`formatField`, `formatNumber`, `formatCurrency`, `flt`, `getFormatDefaults`, `setFormatDefaults`) | Formats numbers, currency and dates for display |
| Field types (`@framework/ui/fields`: `registerFieldType`, `getFieldComponent`, `useFieldTypes`) | Maps a fieldtype to the component that draws it |
| Form keys (`DocKey`, `ParentDocKey`, `UpdateKey`, `LinkTitlesKey`) | How a field reads the document, writes a value, and shows link titles |
| Change reports | How a form tells its host that a value or a child row changed. Optional: a form works without a host |
| `Link`, `Grid`, `Phone`, `TableMultiSelect` | Field controls with their own pickers and tables |
| `ActivityTimeline` (`@framework/ui/ActivityTimeline`: `ActivityTimeline`, `useActivityTimeline`, `reloadActivityTimeline`, `addPendingActivity`, `compareActivities`) | A record's activity feed, its row types, and one listener per record room for feed rows and docinfo |
| `Composer` (`@framework/ui/Composer`: `CommentComposer`, `EmailComposer`) | Comment and email editors, and the payload each sends |
| `FileUpload` (`@framework/ui/FileUpload`: `FileUploadDialog`, `AttachmentsList`, `UploadTray`, `useUploader`, `defaultTransport`, `registerUploadSource`, `UploadLimitsKey`) | Upload dialog, attachment list and tray, with a swappable transport and limits that have a default |
| `Filter`, `QuickFilter`, `ConditionBuilder` | Edit list filters, and their address and wire format |
| `SortBy` | The list sort control and its `order_by` string |
| `ColumnSettings` | Pick, order and size list columns |
| `experimental/List` (`List`, `ListFooter`, `ListBulkBar`) | A virtual-scroll list with selection and a bulk bar |
| `ListView` and `usePagedList` | An app's own paged list: rows a page at a time |
| `useLinkSearch` | The server's matches for a link picker; the last answer wins |
| `Notifications` | The notification panel and its data |
| `InviteUser` | Invite users. The app passes the address to land on |
| `DataImport`, `Onboarding`, `SignupBanner`, `TrialBanner`, telemetry | App-level parts that know about a Frappe backend or Frappe Cloud |
| Islands (`@framework/ui/island`) | Mount a Vue island inside a page that desk v2 does not draw |

### 5. Desk services and registry

| Concept | What it is |
| --- | --- |
| Boot (`Boot`, `fetchBoot`, `BootUnauthorized`) | The small start-up payload for a prefix. Nothing draws before it |
| Navigation shapes (`NavigationItem`, `Navigation`) | One rail or sidebar row, and the rail plus every sidebar |
| Address table (`fetchAddresses`) | Each doctype's slug and module, keyed by `metadata_version` |
| Route builders (`routeFor`, `routeForModule`, `urlFor`, `isModular`) | Build a link to a list, a record or a module. Honour page replacements |
| Shell slot (`registerShell`) | Holds boot, addresses and the router, so `routeFor` works without arguments |
| Arrangement (`fetchArrangement`, `saveArrangement`, `resetArrangement`, `move`) | Read, save and reset the order of rail and sidebar items |
| Module contents (`fetchContents`, `useContents`, `ContentEntry`) | What a module holds, filtered for the user |
| Translations (`loadTranslations`, `__`, `__n`) | Fetch the messages at start, and translate a string or a plural |
| Icons (`Icon`, the sprite) | One SVG sprite, loaded once, and the component that draws a symbol or an emoji |
| Latest reply wins | *New.* One helper for every "only the newest answer counts" guard |
| Per-user browser memory | *New.* One helper for every value kept in browser storage for one user |
| `virtual:frappe/contributions` | The build's index of every app's contributed files |
| Contributions (`Contributions`, `DoctypeContribution`, `RecordHandlers`) | Everything an app may add: doctype handlers, pages, item kinds, replacements |
| List handlers (`listHandlersFor`) | Per-doctype list changes, such as extra columns |
| Page registrations (`pages`, `replacementFor`) | The page for each address. Standard pages are the default registration; an app's page replaces one. The last app wins |
| Item kinds and the item contract (`itemRenderers`, `ItemRenderer`, `Rendering`, `ItemContext`) | What an app's `item.js` implements to draw a navigation item. The last app wins |
| `registerContributions(appOrder)` | Runs once before the first route, in app order |

### 6. Shell

| Concept | What it is |
| --- | --- |
| `AppShell` | The root component: rail, sidebar, page area, and the customize dialog |
| `PageFrame` | The frame every page draws inside: header, scroll area, gutter |
| Page states | Loading, empty, empty with a filter, not found, no permission, offline, failed, each with a retry. Home, list and record share them |
| Rail and sidebar (`RailColumn`, `SidebarPanel`, `SidebarRow`, `SidebarEdge`) | Draw the rail, the sidebar tree and its drag edge |
| `CustomizeSidebarDialog` | Reorder and hide rail and sidebar items, per user or per site |
| Hash dialogs (`useHashDialog`) | A dialog addressed by `#...` in the address, so Back closes it |
| Logout (`logout`, `LogoutDialog`) | End the session, and go to login with a way back |
| Composer state (`composerState`, `openComposer`, `closeComposer`) | Which record's composer is open, with which writer, docked or floating |
| Composer drafts | Unsent comments and emails, per record and writer |
| Composer registration | A record page registers its record, its dock and its writers, so the composer can outlive the page |
| `ComposerWindow` | The composer card, docked or floating |
| Socket (`createSocket`, `repairRooms`) | Opens the realtime socket and hands it to `ui/` |
| Item lookup (`rendererFor`, `renderingOf`, `labelOf`, `iconOf`, `itemContext`) | Draws an item through its kind's renderer |
| Current item (`navigationDestinations`, `currentFrom`) | Which rail item and sidebar the current address belongs to |
| Section memory | Which sidebar sections a user opened or closed |
| Sidebar memory | Which sidebar this tab last showed for an address |
| Item tree (`buildTree`, `useItemTree`) | Turns flat navigation rows into a tree |
| Router (`createShellRouter`, `contributedRoutes`) | The route table from boot, addresses and page registrations |
| Page loader (`mainPageFor`, `loadedPage`) | Loads the registered page for an address while the frame already shows |
| Failed page | Which page's code failed to load |

### 7. Page engines

**The list engine** (`frontend/src/list/`)

| Concept | What it is |
| --- | --- |
| `useListPage` | Everything a list page needs: meta, columns, filters, sort, rows, settings, delete |
| `useListRows` | Rows and a total for one query, a page at a time |
| List settings (`useListSettings`) | Saved columns, sort and quick filters, per user or site. Clears itself on `doctype_update` |
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
| `RecordPageHost` | The contract a page fills: document, save, tabs, feeds, composer. The engine draws nothing |
| Script registry | The registered handlers per doctype and source |
| Source context | Which source is registering or running now |
| `Surface` | A list surface records a script's acts and replays them over the built-ins |
| Staging | Acts wait during a replay and appear at one commit |
| Paint gate | When the page first paints, how a late `onRefresh` lands, and the one repaint for background reads on a return visit |
| Held acts | *New shape.* One queue of script acts (open, close, tab, focus) that runs after the commit |
| Commit channel | Turns a field change into a handler key (`qty`, `items.qty`, `items.onAdd`) and runs it |
| Field and form tab overlays | Changes keyed by fieldname or tab identity |
| Header projection | Turns the header list into two zones, nesting and overflow |
| Frame and body projection | Orders frame bands and works out body column widths |
| Form join | Joins the Details layout with the parts a script adds |
| Form layout source (`useFormLayout`) | One fetch per doctype and layout type; picks the matching row. Clears itself on `doctype_update` |
| Script loader | One loader per doctype for file scripts and stored scripts. Reloads when a stored script changes |
| Page permissions | Rights, roles and field access, ready before handlers run |
| Read-only guard | Objects handed to scripts refuse writes and name the verb to use |
| Error reports | One Error Log row per script failure, by tier |
| Page dialogs | The engine behind `page.dialog` |
| Row handles | Child row handles that find their row again, and refuse once it is gone |
| Feed surfaces | The engine behind `page.activity` and `page.files` |
| Composer surface (`ComposerHost`) | `page.composer`, over a host that owns the composer state |
| Icon and prop hooks (`setIconSource`, `setDrawnProps`) | The record page hands the engine an icon lookup and frappe-ui's prop names when it registers |

### 8. Pages

**Pages other than the record page**

| Concept | What it is |
| --- | --- |
| `Home` | The prefix's landing page: module tiles |
| `Module` | One module's contents |
| `MainPage` | Shows the registered page for a list or record address |
| `List`, `DoctypeList` | The standard list page, built on `useListPage` |
| `DeleteDialog` | Confirm a bulk delete and report failures |
| `TileGridSkeleton` | The loading skeleton for Home and Module |
| App pages | Pages an app contributes or uses as a replacement. They may import only the [import list](#9-customization) |

**The record page** (`pages/Record.vue`, `pages/record/`)

| Concept | What it is |
| --- | --- |
| Record page host (`Record.vue`) | Fills `RecordPageHost`: loads, saves, and wires layouts, feeds, tabs and the composer |
| Visit | *New.* One object per visit to a record. A reply that belongs to an old visit is dropped |
| Return-visit parts | *New.* Which record parts a return visit needs before it paints from memory |
| Record source | The load, the parts re-read, the save, and a cached read |
| Meta source | The doctype meta as one promise or its current value |
| Refetch merge | Merges a background re-read into the draft the reader is editing |
| Save conflict (`SaveConflict`) | The error when someone else saved first, and the fields the reader would lose |
| Live scripts | Re-runs the page's scripts when a stored script of its doctype changes |
| Record feeds (`RecordFeeds`) | The data behind `page.activity` and `page.files`, with the feed's first-paint functions |
| Record tabs (`RecordTabsHost`, `useRecordTabs`) | The four built-in tabs, and the tab named in the address |
| Panel context (`PanelContextKey`, `DocInfo`) | What the built-in panel sections read |
| Panel entries | Joins panel items with the Side Panel layout |
| Panel disclosure | Which panel sections are open |
| Built-in actions | Framework quick actions and menu rows, offered by right |
| Composer host (`composerHost`, `openWriterContext`) | Joins `page.composer` to the shell's composer, and gives a writer its record |
| Writers | *New shape.* One pipeline for the comment and email writers and their drafts |
| Body columns | Column widths and collapse, per user |
| Form tab memory | The last form tab per doctype, per user |
| Dock height | The docked composer's height, per user |
| Docinfo readers | Assignees, shares, tags, favourites and follow, and their actions |
| Remote search | Server search for the user and tag pickers; the last answer wins |

### 9. Customization

What an app author or a site's script author writes. [`SCRIPTING.md`](./SCRIPTING.md) is
the reference for each `page` member.

| Concept | What it is |
| --- | --- |
| File script (`record.js`) | An app's `export default { ... }` handlers for a doctype |
| Stored script | A `Client Script` row with `view = Record`. The same module shape, run from the database |
| Tiers and run order | The owner app's handlers, then other apps' file scripts, then stored scripts. Later tiers win |
| `*` doctype key | Handlers that run on every record, before the doctype's own |
| Handlers and `Handler` | Keys are event names or fieldnames; each value is `(page, row?)` |
| Lifecycle events | `onRefresh`, `beforeSave`, `afterSave`, `onTabChange`, `onFormTabChange`, `onPost` |
| Field change handler | A fieldname key runs when that field's value changes |
| Child table block | Handlers under a table fieldname: field keys, `onAdd`, `onRemove` |
| `SAVE_VETO` | Throwing in `beforeSave` cancels the save and keeps the draft |
| Document (`page.doc`, `page.saved`, `page.isDirty`, `page.doctype`, `page.docname`) | The draft, the last saved copy, and whether they differ |
| `page.meta` | The doctype meta, read-only |
| Rights (`page.perms`, `page.roles`, `page.fieldAccess()`) | The user's rights, roles, and field access |
| Page acts (`page.save()`, `page.reload()`, `page.refresh()`, `page.call()`, `page.router`, `page.toast`) | Save, re-read, re-run `onRefresh`, call a method, navigate, show a toast |
| Surface verbs (`add`, `hide`, `show`, `update`, `move`, `has`, `order`, `clear`, `Position`) | The same verbs on every list surface |
| Built-in item names | The names a script hides or moves: frame, body, tabs, panel sections, actions, writers |
| `page.quickActions`, `page.header`, `page.frame`, `page.body`, `page.tabs`, `page.panelSections` | The regions of the page around the form |
| `page.form`, `page.form.tabs`, `page.fields`, `page.rows()` | The Details form, its tabs, field properties, and child rows |
| `page.activity`, `page.files`, `page.composer`, `page.dialog` | The feed, the attachments, the writers, and dialogs |
| List file (`list.js`) | An app's changes to a doctype's list, such as extra columns |
| Item file (`item.js`) | An app's renderer for one kind of navigation item |
| Import list | The one list of names that customization code and app pages may import |

**The import list.** App files and stored scripts share one list:

| Name | What it gives |
| --- | --- |
| `vue`, `vue-router`, `frappe-ui` | The framework's shared packages |
| `@framework/ui` | All of `ui/` while the `"./*"` entry stays |
| `frappe/i18n` | `__` and `__n` |
| Desk names | `routeFor`, `routeForModule`, `urlFor`, `RouteOptions`, `isModular`, `ContentEntry` |
| App names | Names an app publishes through its `import_map` hook |

A script reaches the rest of the desk only through the `page` object it is handed.

### Outside the layers

**`main.ts`**

| Concept | What it is |
| --- | --- |
| Start sequence (`start`) | Boot, then translations and icons without waiting, then addresses, contributions, standard pages, router, socket, and mount |
| What the desk hands `ui/` | The session, the CSRF token, the socket, upload limits, and the invite address |

**The build**

| Concept | What it is |
| --- | --- |
| `build_shell` | `bench build` writes the manifest, installs packages if needed, builds once, and swaps the output in |
| One vite config | One build for all apps, served at `/assets/frappe/frontend/` |
| Aliases (`@/`, `@shell`) | `@/` is private to the framework; `@shell` gives app files the desk names |
| Manifest | The apps that add to the desk, their folders and packages. Moves here from `frappe/shell/` |
| Shared packages (singletons) | Packages every app must share one copy of. A conflict stops the build |
| `desk.package.json` | An app's declared frontend packages, merged into one `package.json` and lockfile |
| Contribution layout and discovery | The file paths that count as contributions, and the walk that finds them |
| Replacement pages (`pages.json`) | A doctype's `pages.json` replaces its standard list or record page |
| Page clash warnings | Warns when a page slug equals a doctype or module slug |
| One tree | An app's bare imports resolve from the framework's `node_modules`, only if declared |
| Import map | Points each name on the import list at a built file |
| `classes.json` | Every CSS class the build defines |
| Tailwind presets and content | Each app's theme preset, and the folders Tailwind reads |
| `ui/vite` | The vite plugin for apps that use `@framework/ui` |

## The five flows

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
| 4 | The server builds boot: core keys, session, `metadata_version`, prefix map, and the rail and sidebars filtered for the user | 2, 1 | App permission; each navigation row filtered by readable doctypes, modules and pages | Session in Redis by session id; `metadata_version` and prefix map in the site cache; navigation not cached |
| 5 | Translations and the icon sprite start, not awaited | 5 | None | HTTP cache, 1 year, by language and translation version. The sprite is a static file |
| 6 | The address table loads, awaited | 5, 3, 2 | The user may enter at least one app | One server cache key, checked against `metadata_version`. HTTP cache, 1 year, by `metadata_version` |
| 7 | `main.ts` registers the standard pages. Contributions register item kinds, app pages, replacements and handlers. The record page registers its icon and prop hooks | 5, 7 | None | Browser memory, by item kind, by address kind and doctype, by doctype |
| 8 | The router is built from boot, addresses and page registrations | 6 | None. The router checks only that an address names a known doctype | Browser memory |
| 9 | The socket opens and is handed to `ui/`. The desk hands `ui/` its session. Each cache of site data listens for `doctype_update` itself | 6, 3 | Realtime server: the user room; the site room for System Users only; each document room by read permission | Session store in browser memory |
| 10 | The shell draws the rail and sidebar, before any page code arrives. Each row is drawn by its kind's renderer | 6, 5 | **Browser**: none; the rows were filtered in step 4 | Per-user browser memory: open sections, collapsed sidebar. Sidebar memory per tab, by address and user |
| 11 | The home page loads the app's contents and draws its tiles, or a page state | 8, 5, 2 | App permission; readable doctypes only | None |

**Budget:** first paint time; boot size; `get_boot` time on the server; no request sent
twice; layout shift; the shell drawn before the page's code arrives; a change on screen
soon after any click.

### Open a list: sidebar click to rows painted

| # | Step | Layer | Permission check | Cache and key |
| --- | --- | --- | --- | --- |
| 1 | A sidebar row's link, built with `routeFor`, is clicked | 6, 5 | None | None |
| 2 | The router checks the slug against the address table | 6 | None: an address check, not a permission check | Browser memory |
| 3 | The address and the frame change at once. The page shows its skeleton while the registered page's code loads | 6 | None | Loaded pages in browser memory |
| 4 | The list page asks for the doctype's meta. Roles come from the session | 7, 3 | Any signed-in user | Browser memory, by doctype; cleared on `doctype_update` |
| 5 | The list loads its saved settings (the site row and the user's row) and works out columns, sort and quick filters | 7, 3 | Read on the doctype; System Manager for the site row. **Browser**: columns on fields the user cannot read are dropped | Browser memory, by doctype; cleared on `doctype_update` |
| 6 | The rows are read, with the count on the first page | 7, 3, 1 | Doctype read, row rules and field permissions in the query | Data cache, by doctype and query. Rows memory, by doctype. Page size and scroll in the history entry |
| 7 | The rows paint and the scroll is restored. The column and sort panels load only when opened. An empty or failed read shows a page state | 4, 7, 8 | None | As step 6 |

**Budget:** on a cold load, time until usable, request count, JS size. On a return visit,
skeleton frames, time until usable, re-reads.

### Open a record: row click to the record page painted

| # | Step | Layer | Permission check | Cache and key |
| --- | --- | --- | --- | --- |
| 1 | The row link goes through the same router steps as the list. The frame changes at once | 6 | None | Loaded pages in browser memory |
| 2 | The record page starts a visit: skeletons, the last form tab, and the record's room | 8, 3 | Realtime server: read permission on the room | Per-user browser memory: form tab by doctype |
| 3 | In parallel, the script loader starts (see the last flow) and the two form layouts load | 7, 3 | Layouts: read on the doctype | Scripts by doctype; layouts by doctype and type; both cleared on `doctype_update` |
| 4a | Return visit: if memory holds every part the visit needs, the page paints from memory at once, then re-reads. Background reads land in one repaint | 8, 3 | None before the paint. The re-read carries the server check. A refusal shows the "no permission" page state | Data cache, by doctype and name |
| 4b | First visit: the activity read starts beside the record read | 8, 3 | Read permission on the record | Activity store, by record |
| 5 | The record is read with its parts and meta, and goes into the data cache | 8, 3, 1 | Read permission and field-level read rules | Data cache, by doctype and name; meta by doctype |
| 6 | The engine builds `page` with its rights, roles and field access | 7 | **Browser**: field access by permission level. The server checks it again on save and on every read | Handlers by doctype |
| 7 | Built-in actions are offered by right: email, print, tags, attach, delete, share, assign | 8 | **Browser**, by right. The server checks each action | None |
| 8 | First paint: the page waits for layouts, feed and scripts, runs one replay, paints, then runs held acts | 8, 7 | None | None |
| 9 | Header, body, tabs, form, panel and feed draw. Saved comments show as cleaned HTML; the editor loads only to write | 8, 4 | None beyond steps 6 and 7 | Per-user browser memory: open sections, body columns, dock height |

**Budget:** on a cold load, time until usable, request count, JS size, paints. On a return
visit, skeleton frames, time until usable, re-reads, paints.

A record shown from memory after its access was removed is accepted. The same user saw
that copy in the same tab, and the page shows "no permission" once the server replies.

### Save: edit a field and save, to the saved state shown

| # | Step | Layer | Permission check | Cache and key |
| --- | --- | --- | --- | --- |
| 1 | A field changes. `FormLayout` writes the value into the draft and reports the change | 4 | **Browser**: a field the user cannot write is read-only | None |
| 2 | The engine's commit channel drops repeats and runs the field's handlers | 7, 9 | None | None |
| 3 | Save, from the button or from Ctrl+S, takes one path: one saving state, and the same paint hold. The engine runs owed changes, `beforeSave`, the page's save, then `afterSave` | 8, 7, 9 | None. Save is offered to every reader; the server decides | None |
| 4 | The page sends the draft with `modified`, one request at a time. It refuses if the visit has changed | 8, 3 | None | None |
| 5 | The server saves: write check, timestamp check, higher permission levels reset, a version row, and `doc_update` after the commit. The reply has field-level read rules applied | 1 | Write permission; field permission levels; field-level read on the reply | None |
| 6 | The reply goes into the data cache. On a timestamp conflict, the page re-reads the record and asks the reader what to do | 3, 8 | The re-read checks read permission | Data cache, by doctype and name, in request order |
| 7 | The page shows the saved state with a visible confirmation, re-reads the side parts, and replays surfaces and handlers | 8, 7, 3 | Read permission on the re-read | Data cache |
| 8 | The record room's listener hears `doc_update`, and the feed re-reads its newest page | 4, 3 | Room and feed read permission | Activity store |

**Budget:** time until the saved state shows; request count; a visible confirmation.

### Load a stored script onto a record page

| # | Step | Layer | Permission check | Cache and key |
| --- | --- | --- | --- | --- |
| 1 | A record visit asks the script loader for its doctype's scripts, beside the record read | 8, 7 | None | One entry per doctype; the latest load wins |
| 2 | The loader fetches the enabled stored scripts for the Record view | 7, 3 | None | Not HTTP-cached |
| 3 | The server checks read on the doctype, reads enabled rows in run order, drops rows of disabled modules, and says whether the user may write scripts | 1 | Read permission on the doctype; write permission on `Client Script` for the answer | Disabled modules, per request |
| 4 | The loader keeps the write answer. Only a script writer sees failure toasts and the editor entry | 7 | **Browser**. The server checks `Client Script` write on save | Browser memory |
| 5 | Each script loads as a module; its bare imports resolve through the import list. Its handlers register under its name, beside the app's file scripts. A failing script is skipped and reported | 7, 9 | None | Browser module map |
| 6 | The engine holds the first paint until the scripts are in or 500 ms pass, then replays | 7 | A script's own checks on `page.roles` or `page.perms` only change what is shown | None |
| 7 | A saved, reordered or deleted script sends `client_script_changed` to the site room. The loader drops its entry, and an open record page with no unsaved edits re-runs its scripts | 1, 7, 8 | The site room admits System Users only | The doctype's entry is dropped |

**Budget:** the first paint waits at most 500 ms for stored scripts.

## Where the code is not there yet

Each row is a place where today's code breaks this file. The PR that closes a row
removes it.

**Layer breaks and moves**

| Today | Target | Owner |
| --- | --- | --- |
| `get_url_to_form` in `frappe/utils/data.py` imports `frappe/shell/links.py`, and there are two record address builders | One record address builder in layer 1 | New map for the shell, list, router and server routes |
| `frappe/bundler.py` imports `frappe/shell/manifest.py` | The manifest code the bundler needs moves into the build | New map |
| The shell page renderer is in `frappe/website/page_renderers/` and imports `frappe/shell/` | It moves into `frappe/shell/`, found through the `page_renderer` hook | New map |
| `routeFor` is in `router/` and the item contract is in `navigation/types.ts` | Both move to layer 5 | New map |
| `contributions/registry.ts` imports `@/recordPage` to hand over record handlers | The script loader reads the registry | One page model |
| `shell/ComposerWindow.vue` imports the writers from `pages/record/composer/`; `shell/composer.ts` imports types from `@/recordPage` | The record page registers its writers | Activity column |
| `shell/doctypeUpdates.ts` imports the layout and list settings caches | Each cache clears itself on `doctype_update` | Build and publishing |
| `router/generated.ts` and `router/standardPages.ts` import the pages | The router reads page registrations | New map |
| `main.ts` sets the record page's icon and prop hooks | The record page sets them when it registers | Build and publishing |
| `useSession`, `useDoctypeMeta`, `useDocPermissions` and `useUserRoles` sit in the component layer | They move to `ui` data | @framework/ui |
| Two import lists: the `import_map` hook for stored scripts, `@shell` for app files | One import list | Build and publishing |

**Concepts that change**

| Today | Target | Owner |
| --- | --- | --- |
| Nine visit guards in `Record.vue`, and 11 hand-written "latest reply" counters | One visit; one "latest reply wins" helper | One page model; new map |
| Five stores of held script acts | One queue | One page model |
| Two listeners on each record room | One | Activity column |
| Two save paths; Ctrl+S skips the paint hold | One save path | One page model |
| Separate comment and email writer pipelines | One | Activity column |
| Three sets of loading and error states | One set of page states | New map |
| The router waits for the next page's code | The frame changes at once | New map |
| Six copies of per-user browser memory code | One helper | One page model; new map |
| Two server cache keys for doctype owners and the address table | One | New map |
| First app wins for item kinds; last app wins for replacements | Last app wins everywhere | Build and publishing |
| File scripts and stored scripts load in two ways | One loader | One page model |
| The session fetched twice | The desk passes it | @framework/ui |
| Record page words in four `ui/` files, and the commit channel in `ui/` | Both in `frontend/` | @framework/ui |
| The editor loads to show saved comments | Cleaned HTML; the editor loads to write | Activity column |
| The list's column and sort panels load with the list | They load when opened | New map |
| The tombstone code in `recordPage/pageCompatibility.ts` for an empty list | Gone; the rule stays in `COMPATIBILITY.md` | One page model |
| Dead code: `resolveDoctype`, `currentNavigation`, `forgetRows`, `clear_address_table`, `clear_doctype_owners`, `setDocValueReader`, `reloadClientScripts`, a second loader in `useFormLayout.ts` | Gone | New map |
| The currency lookup keeps its own map that never refreshes | It reads the data cache | Return visits |

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

Kept for now, and decided again when `onOpen` is built: the late part of an async
`onRefresh`, and acts from `onRefresh`.
