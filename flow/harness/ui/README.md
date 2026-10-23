# Flow web UI

Two packages (npm workspaces):

- **`core/`** — `@flow/ui-core`: the daemon client (HTTP + SSE), the transcript
  reducer, and the chat components (Vue 3, styled with frappe-ui tokens only).
  Shipped as source; the consuming app compiles the `.vue` files and Tailwind
  classes. The Flow Frappe app imports these same components for its full-page
  UI and swaps `DaemonClient` for a proxy-backed one.
- **`app/`** — the standalone web shell: connect screen, theme, Vite dev server
  with a proxy to the daemon (it has no CORS middleware, so the app must be
  same-origin or proxied).

## Run

Production-style — one command, UI served by the daemon itself (same origin):

```bash
cd ui && npm install && npm run build -w app   # builds into src/flow_harness/server/webui/
flow web
```

Development — Vite dev server with HMR, proxying to a separate daemon:

```bash
cd ui && npm install
flow serve            # daemon on 127.0.0.1:8787 (or FLOW_DAEMON_URL)
npm run dev -w app
```

## Host options

`createFlowStore(client, options)` takes what a host without a daemon
filesystem must change, so it can reuse the components instead of copying them:

- `requireCwd` — `false` sends without a project folder.
- `storageKey` — localStorage prefix (`flow.ui`), scoped per user by the host.
- `maxAttachments` — per-message cap of the host's upload path.
- `skillsEnabled` — `false` skips skill catalog requests and hides skill
  suggestions/highlighting in the composer; defaults to `true`.
- `workspace` — `false` when the host mounts no workspace panel: a sub-agent's row
  then expands in place instead of opening the child's thread in a tab.
- `presentTool(name, args)` — `{ icon, label, subject, title, body, argsComponent }`, any
  subset, for the host's own tools in transcript rows and approval cards.
- `turnActions` — a component rendered after each finished turn's copy button, with
  `turnKey`, `text` and `ts` props (Flow's feedback thumbs).
- `listedModel` — `true` when a session-list row's `model` is the chat's current one,
  so a chat being opened shows it before it loads; defaults to `false` (the daemon's
  list can lag a model change).
- `colorScheme` — frappe-ui's `useColorScheme()`, for a host whose daemon keeps the
  settings (`client.settings`): the theme is then saved and restored with them.

The store exposes `capabilities.rewind` when its client implements `rewind`.
Both the message action and composer command follow that capability. A session
whose info sets `read_only` shows no message action, and neither does a message
not in the log yet or one steered into a running turn; for a steered one, `/rewind`
takes that run's own message.

A client can implement `prepareAttachment(file)` returning `{ id, name, kind }`
and `discardAttachments(ids)` to prepare uploads before a session exists.
The composer shows progress, waits on pending preparation when sending, and
discards removed uploads. Prepared IDs are reused on send. Clients without
these methods continue uploading on send; discard must preserve files already
claimed by an accepted turn.

`argsComponent` is a Vue component receiving an `arguments` prop. It renders in
expanded tool rows (including rows inside `ToolGroup`) and replaces the default
argument body in approval cards. The card caps its own height and scrolls a
taller view. For example, a host can return
`{ argsComponent: ArgsView }` for its document tools. Omit it to keep the built-in
command text, edit diffs and tool output presentation. Tool results and approval
actions remain available when a custom argument component is supplied.

`Composer` props: `commands` (slash commands offered, in order: built-ins by name,
or a host's own `{ name, label, icon, hint, view }`; default all built-ins),
`mentions` (`@` file mentions), `imagesOnly` (`false` lets the picker take any
file when the host stages uploads itself), `placeholder` (the textarea's hint),
`modes` (the approval modes as `{ id, label, desc }`, worded for the host's
tools), `disabled` (shown but inert, every control included). `ChatHeader` takes `workspace` (`false` when the host mounts no file
panel). `MessageList` has an `empty` slot for the host's own empty state, and a
`conversation` prop to draw a thread other than the session's (the workspace panel
draws a sub-agent's this way). Selecting text in either thread shows an "Add to chat"
pill that quotes it under the next message.

`WorkspacePanel` is a shell as well: the tab strip, the window controls and a
sub-agent's thread are shared, and three slots take the host's own views. `actions`
sits at the end of the tab strip (the harness passes its "+" menu of Files and Diffs),
`view` draws any tab that is not a sub-agent's, scoped with the `tab` (`null` while
a Files or Diffs view has no file open; the harness passes `EditorView`), and `empty`
fills the panel when nothing is open. A host that only shows sub-agent threads passes an
`empty` state and nothing else.

`Composer` also has a `toolbar` slot: the pickers after the attach button. It
defaults to `ModelButton`, and is scoped with `openPalette(view)` so a host's own
pickers can sit beside it:

```vue
<template #toolbar="{ openPalette }">
	<AgentPicker @open="openPalette" />
	<ModelButton @open="openPalette" />
</template>
```

A host's own command, or a picker calling `openPalette(view)`, opens the `palette`
slot, scoped with `view`, `close()` and `back()` (to the commands list); the host
renders its page above the composer when `view` is its own:

```vue
<template #palette="{ view, close, back }">
	<AgentPalette v-if="view === 'agents'" @close="close" @back="back" />
</template>
```

`SettingsDialog` is a shell: the dialog, its sidebar and its type scale are shared,
while each host names its tabs in `groups` (`[{ label, tabs: [{ id, label, icon }] }]`)
and fills one slot per tab id with its own panel, built from `SettingsPage` (a heading
and body that scroll together; `back` adds a way back for a page that replaced another,
the `actions` slot sits at the heading's right, and a `footer` slot is pinned under the
body) and
`SettingsRow` (a setting and its control). `v-model:tab`
opens a given tab. On phones the first group's label row carries the close button. The harness passes its four tabs from `FlowChat`; the Flow Frappe
app passes its doctype panels.

## Notes / gaps against the daemon API

- Session titles, delete, the context meter, provider setup (API keys + OAuth),
  and the `/cwd` folder picker are all served by the daemon (`title` in
  listings, `DELETE /sessions/{sid}`, `context_window`/`context_tokens` on the
  session detail, `/providers/*`, `GET /fs/pick`).
- The approval-mode picker applies to sessions created from then on;
  `auto_approve` is fixed at session create.
- The composer supports image uploads and pasted images. PNG, JPEG, GIF, WebP, and BMP
  images are snapshotted into session-scoped attachment storage before the message is sent.
- Serving the UI from a different origin without a proxy needs
  `FLOW_CORS_ORIGINS=<origin>` on the daemon.
