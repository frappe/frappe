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
- `presentTool(name, args)` — `{ icon, label, subject, title, body, argsComponent }`, any
  subset, for the host's own tools in transcript rows and approval cards.

`argsComponent` is a Vue component receiving an `arguments` prop. It renders in
expanded tool rows (including rows inside `ToolGroup`) and replaces the default
argument body in approval cards. For example, a host can return
`{ argsComponent: ArgsView }` for its document tools. Omit it to keep the built-in
command text, edit diffs and tool output presentation. Tool results and approval
actions remain available when a custom argument component is supplied.

`Composer` props: `commands` (slash commands offered, by name; default all),
`mentions` (`@` file mentions), `imagesOnly` (`false` lets the picker take any
file when the host stages uploads itself). `ChatHeader` takes `workspace`
(`false` when the host mounts no file panel).

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
