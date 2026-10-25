import { reactive, watch } from "vue"

import { FlowAPIError } from "./client.js"
import { CHAT_FONT_SIZE, CHAT_FONT_WEIGHT, layout } from "./layout.js"
import {
	applyEvent,
	approvalToAnswer,
	conversationTitle,
	initialConversation,
	modelTitle,
	normalizeSkillCommand,
	skillCommand,
	subagentTitle,
	waitingApprovals,
} from "./transcript.js"

// mirrors MAX_ATTACHMENTS_PER_MESSAGE on the daemon; the client has no endpoint to
// learn it from, so it is restated here and enforced before anything is staged
export const MAX_ATTACHMENTS = 10

function sameArray(left, right) {
	return left.length === right.length && left.every((value, index) => value === right[index])
}

// the same files in any order: a host's echo can list inlined files after the rest
function sameFiles(left, right) {
	return sameArray([...left].sort(), [...right].sort())
}

function attachmentNames(content) {
	const blocks = Array.isArray(content) ? content : []
	return blocks.filter((block) => block.type === "attachment").map((block) => block.name)
}

// A run that ended on its own hands the queue its next turn; a pause, a stop, a failure
// or a denied tool call leaves the queue waiting for the user.
function ranItsCourse(reason) {
	return !!reason && !["paused", "aborted", "error", "denied"].includes(reason)
}

function readJSON(key, fallback, storage = globalThis.localStorage) {
	try {
		return JSON.parse(storage.getItem(key)) ?? fallback
	} catch {
		return fallback
	}
}

const isPreset = (preset) => preset && typeof preset.id === "string" && Array.isArray(preset.tools)
const same = (left, right) => JSON.stringify(left) === JSON.stringify(right)
const copy = (value) => JSON.parse(JSON.stringify(value))

// The prefs a daemon that keeps settings (client.settings) saves with the presets and the
// theme, so they outlive the browser's storage and follow the user to another browser. The
// rest (panel sizes, open folders, the folder for new chats) belong to this browser.
const SYNCED_PREFS = [
	"mode",
	"customInstructions",
	"activePreset",
	"defaultPreset",
	"lastModel",
	"lastEffort",
	"sidebarGroup",
	"sidebarOrder",
	"chatOrder",
	"folderOrder",
	"chatFontSize",
	"chatFontWeight",
]
const COLOR_SCHEMES = ["system", "light", "dark"]

// One store per connected daemon. `client` implements the DaemonClient surface;
// Flow's Frappe shell passes a proxy-backed client instead.
//
// Host options:
//   requireCwd     false lets a host without a filesystem send without a folder
//   storageKey     localStorage prefix, so a host can scope saved state per user
//   maxAttachments per-message cap enforced by the host's upload path
//   skillsEnabled  false disables skill catalog requests and composer suggestions
//   workspace      false when the host mounts no workspace panel: a sub-agent's row then
//                  expands in place instead of opening the child's thread in a tab
//   presentTool    (name, args, result) => { icon, label, subject, stat, expandable, title,
//                  body, argsComponent, resultComponent }, any subset, describing the host's
//                  own tools in rows, approvals and expanded output. Both components fill
//                  their panel and carry their own padding; resultComponent takes the panel
//                  over from the text dump, and expandable: false drops the dropdown
//   turnActions    a component rendered after each finished turn's copy button, with
//                  the turn's key, response text and timestamp as props
//   listedModel    true when a session-list row's `model` is the chat's current one, so a
//                  chat being opened shows it before it loads (the daemon's can lag)
//   colorScheme    frappe-ui's useColorScheme(), for a host whose daemon keeps the theme
//                  with the other settings
export function createFlowStore(client, options = {}) {
	const capabilities = { rewind: typeof client.rewind === "function" }
	options = {
		requireCwd: true,
		storageKey: "flow.ui",
		maxAttachments: MAX_ATTACHMENTS,
		skillsEnabled: true,
		workspace: true,
		presentTool: null,
		...options,
	}
	const keys = {
		prefs: `${options.storageKey}.prefs`,
		titles: `${options.storageKey}.titles`,
		workspace: `${options.storageKey}.workspace`,
		presets: `${options.storageKey}.presets`,
		queue: `${options.storageKey}.queue`,
		synced: `${options.storageKey}.synced`,
	}
	// theme lives in frappe-ui's useColorScheme (localStorage "theme"), not here; a host whose
	// daemon keeps settings passes it in (options.colorScheme) to save and restore it with them
	const defaults = {
		mode: "ask", // "ask" | "auto" — applied at session create
		customInstructions: "", // sent as system_suffix at session create
		activePreset: null, // id of the agent preset applied to new chats
		defaultPreset: null, // { tools, extensionTools } ticked for the Default preset on top of the core tools
		lastModel: null,
		lastEffort: null,
		cwd: null,
		sidebarOpen: true,
		sidebarWidth: 288,
		openFolders: [], // the sidebar's expanded workspace folders
		sidebarGroup: "workspace", // "workspace" | "list": the sidebar's chats under their folders, or in one list
		sidebarOrder: "updated", // "updated" | "manual": newest activity first, or as dragged
		chatOrder: [], // session ids in their manual order
		folderOrder: [], // workspace folders in their manual order
		workspaceWidth: 460,
		explorerWidth: 220,
		chatFontSize: CHAT_FONT_SIZE.default,
		chatFontWeight: CHAT_FONT_WEIGHT.default,
	}
	// only what differs from these is saved, so a setting left alone follows a new default
	const prefs = { ...copy(defaults), ...readJSON(keys.prefs, {}) }
	if (typeof prefs.customInstructions !== "string") prefs.customInstructions = ""

	// the docked sidebar follows the saved preference; a drawer starts closed and is never saved
	const sidebarFromPrefs = () => !layout.narrow && prefs.sidebarOpen !== false

	const state = reactive({
		sessions: [],
		sessionsMore: false, // the host has pages past the last row
		sessionsLoading: false,
		sessionQuery: "", // the title search the list was loaded under
		// the daemon's workspaces, { path, name }: named folders the sidebar groups chats under, a
		// list row's `workspace` being one's path; null when the daemon keeps none
		folders: null,
		sessionId: null,
		session: null, // GET /sessions/{sid} payload
		conversation: initialConversation(),
		queued: [], // the composer's queue: messages waiting for the run to end
		models: [],
		modelsLoading: false,
		modelErrors: [],
		tools: [], // what the daemon lets a session enable: { name, description, extension }
		skills: [],
		loading: false,
		toast: null,
		draft: null, // { text, attachments } handed to the composer after rewind
		codeRefs: [], // { path, rel, start, end } selections queued for the next message
		quotes: [], // thread selections ("Add to chat") quoted under the next message
		// right panel; tabs are typed, keyed by `path` (browser/terminal later) —
		// editor tabs: { kind, path, name, content, error, loading, dirty }, content
		// being the last server-confirmed text (the editor owns unsaved edits);
		// sub-agent tabs: { kind: "subagent", path: the child's id, name: its description }
		workspace: { open: false, maximized: false, tabs: [], active: null, view: null },
		sidebarOpen: sidebarFromPrefs(),
		settingsOpen: false,
		settingsTab: null, // the settings dialog's tab, for a host that binds it; null is its first
		transcriptOpen: false,
		prefs,
		// agent presets: { id, name, tools, extensionTools, promptMode, prompt }
		presets: [].concat(readJSON(keys.presets, [])).filter(isPreset),
		titles: readJSON(keys.titles, {}),
	})

	watch(() => layout.narrow, () => (state.sidebarOpen = sidebarFromPrefs()))

	let stream = null
	let streamTask = null
	let opening = 0 // keys the newest openSession: an older load of the same chat gives way
	let creating = null // { blank, session }: in-flight lazy session creation; a double-send shares it
	let sendCount = 0 // keys the bubbles waiting for the server to echo them
	let queueCount = 0 // keys the queue's rows
	let lastRunEnd = null // the open session's latest run_ended reason
	// waiting messages, as { message, attachments, afterSeq }, of the sessions not open right now
	const heldBySession = reactive(new Map(Object.entries(readJSON(keys.queue, {}, globalThis.sessionStorage))))
	// This tab keeps every session's waiting messages across a reload; sessionStorage, so
	// other tabs don't send them too (a duplicated tab starts with a copy, though).
	watch(
		() => {
			const all = Object.fromEntries(heldBySession)
			if (state.sessionId && state.queued.length) all[state.sessionId] = state.queued.map(waitingRecord)
			return JSON.stringify(all)
		},
		(json) => {
			try {
				sessionStorage.setItem(keys.queue, json)
			} catch {
				// storage blocked: the queue still lasts until the page goes
			}
		},
	)
	let loadingSkills = null // { key, promise }
	let loadedSkillsFor = null // key of the list in state.skills
	let toolsLoading = null // the /tools fetch in flight; a first send waits for it

	// The daemon's settings: the page starts from this browser's copy, then takes the daemon's,
	// except for a setting changed here since the two last agreed, which goes to the daemon
	// instead. A change is saved here at once and there a moment later.
	let agreed = readJSON(keys.synced, null) // what the daemon was last known to hold
	let settingsLoaded = false
	let settingsTimer = null
	let settingsSaving = Promise.resolve()

	function savePrefs() {
		localStorage.setItem(keys.prefs, JSON.stringify(changedPrefs()))
		queueSettings()
	}

	function changedPrefs() {
		return Object.fromEntries(Object.entries(state.prefs).filter(([key, value]) => !same(value, defaults[key])))
	}

	// a setting at its default goes as null, so every browser keeps following the default
	function currentSettings() {
		const current = Object.fromEntries(
			SYNCED_PREFS.map((key) => [key, same(state.prefs[key], defaults[key]) ? null : state.prefs[key]]),
		)
		current.presets = state.presets
		if (options.colorScheme) current.theme = options.colorScheme.colorScheme.value
		return current
	}

	async function loadSettings() {
		let saved
		try {
			saved = (await client.settings()).settings ?? {}
		} catch {
			return // an older daemon, or one whose policy keeps settings off: this browser's copy stands
		}
		const current = currentSettings()
		for (const [key, value] of Object.entries(saved)) {
			if (!(key in current) || (agreed && !same(current[key], agreed[key]))) continue
			if (key === "theme") {
				if (COLOR_SCHEMES.includes(value)) options.colorScheme.setColorScheme(value)
			} else if (key === "presets") {
				// a browser's first sync keeps its own presets beside the daemon's
				const theirs = [].concat(copy(value)).filter(isPreset)
				const mine = agreed ? [] : state.presets.filter((preset) => !theirs.some((their) => their.id === preset.id))
				state.presets = [...theirs, ...mine]
			} else state.prefs[key] = copy(value ?? defaults[key])
		}
		if (typeof state.prefs.customInstructions !== "string") state.prefs.customInstructions = ""
		agreed = saved
		settingsLoaded = true
		localStorage.setItem(keys.prefs, JSON.stringify(changedPrefs()))
		localStorage.setItem(keys.presets, JSON.stringify(state.presets))
		localStorage.setItem(keys.synced, JSON.stringify(agreed))
		saveSettings()
	}

	// a moment after a change; before the first load, the load sends it
	function queueSettings() {
		if (!settingsLoaded) return
		clearTimeout(settingsTimer)
		settingsTimer = setTimeout(saveSettings, 500)
	}

	// one save at a time, of what the daemon lacks; a failed one is sent again with the next
	// change, or by the next load
	function saveSettings() {
		settingsSaving = settingsSaving.then(async () => {
			const changed = Object.entries(currentSettings()).filter(([key, value]) => !same(value, agreed[key]))
			if (!changed.length) return
			const sent = copy(Object.fromEntries(changed))
			try {
				await client.updateSettings(sent)
			} catch {
				return
			}
			agreed = { ...agreed, ...sent }
			localStorage.setItem(keys.synced, JSON.stringify(agreed))
		})
	}

	// the theme used to live in prefs; frappe-ui's useColorScheme keeps it under "theme"
	if ("theme" in state.prefs) {
		if (!localStorage.getItem("theme")) localStorage.setItem("theme", state.prefs.theme)
		delete state.prefs.theme
		savePrefs()
	}

	function notify(message, kind = "info") {
		state.toast = { message, kind, at: Date.now() }
	}

	async function guard(work, { rethrow = false } = {}) {
		try {
			return await work()
		} catch (error) {
			if (error instanceof FlowAPIError) notify(error.message, "error")
			else notify(String(error?.message ?? error), "error")
			if (rethrow) throw error
			return null
		}
	}

	function rememberTitle(sid) {
		if (state.titles[sid]) return
		const title = conversationTitle(state.conversation)
		if (!title) return
		state.titles[sid] = title
		localStorage.setItem(keys.titles, JSON.stringify(state.titles))
	}

	function sessionTitle(info) {
		return (
			info.title ??
			state.titles[info.session_id] ??
			`${(info.cwd ?? "").split("/").filter(Boolean).pop() ?? "session"} · ${info.session_id.slice(0, 8)}`
		)
	}

	// The list comes a page at a time: a refresh reloads the first page under the current
	// query, `more` appends the page past the last row shown, a new query starts over. A
	// host that lists everything at once reports no more. Only the newest request lands.
	let listRequest = 0
	let listQuery = "" // the newest request's query: the box's, even before its answer lands
	async function refreshSessions({ query = listQuery, more = false } = {}) {
		const own = ++listRequest
		listQuery = query
		const before = more ? state.sessions.at(-1)?.modified : undefined
		state.sessionsLoading = true
		const folders = more ? null : refreshFolders()
		let data
		try {
			if (!state.folders) await folders // the daemon makes them as it first lists them
			data = await guard(() => client.sessions({ query, before }))
			await folders // a row lands with the workspace it names
		} finally {
			if (own === listRequest) state.sessionsLoading = false
		}
		if (!data || own !== listRequest) return
		state.sessionQuery = query
		state.sessionsMore = !!data.more
		state.sessions = more ? [...state.sessions, ...data.sessions] : data.sessions
		// a new chat with no folder yet starts in the latest workspace
		const latest = latestFolder()
		if (!state.sessionId && !state.prefs.cwd && latest) setCwd(latest)
		// the open session's row mirrors its loaded detail: the live stream keeps that
		// newer than a list served before an event landed
		const open = state.sessions.find((info) => info.session_id === state.session?.session_id)
		if (open) {
			if (state.session.title != null) open.title = state.session.title
			if (state.session.state != null) open.state = state.session.state
		}
		// drop stored panel state for sessions deleted outside this UI — a session missing
		// from a partial list may just be on a later page
		if (query || state.sessionsMore) return
		const known = new Set(state.sessions.map((info) => info.session_id))
		const stale = Object.keys(workspaceBySession).filter((sid) => !known.has(sid))
		if (stale.length) {
			for (const sid of stale) delete workspaceBySession[sid]
			localStorage.setItem(keys.workspace, JSON.stringify(workspaceBySession))
		}
	}

	function loadMoreSessions() {
		if (state.sessionsMore && !state.sessionsLoading) return refreshSessions({ more: true })
	}

	// silent: an older daemon, or one whose policy keeps them off, leaves chats grouped by folder
	let foldersRequest = 0 // a change drops the lists still on their way: they may predate it
	async function refreshFolders() {
		if (typeof client.workspaces !== "function") return
		const own = ++foldersRequest
		let data
		try {
			data = await client.workspaces()
		} catch {
			return
		}
		if (own !== foldersRequest) return
		state.folders = data.workspaces
	}

	const isFolder = (path) => !!path && !!state.folders?.some((folder) => folder.path === path)

	// the workspace of the latest chat, else the one added last
	function latestFolder() {
		const latest = state.sessions.find((session) => isFolder(session.workspace))
		return latest?.workspace ?? state.folders?.at(-1)?.path ?? null
	}

	// a folder's name in the sidebar: its workspace's, else its own
	function folderName(path) {
		const name = state.folders?.find((folder) => folder.path === path)?.name
		return name ?? path.split(/[\\/]/).filter(Boolean).pop() ?? path
	}

	// an existing folder's workspace, added at once, with no chats yet; null where the daemon keeps none
	async function addFolder(path) {
		if (!state.folders) return null
		const data = await guard(() => client.addWorkspace(path))
		if (!data) return null
		foldersRequest++
		if (!isFolder(data.workspace.path)) state.folders = [...state.folders, data.workspace]
		return data.workspace
	}

	async function renameFolder(path, name) {
		const data = await guard(() => client.renameWorkspace(path, name))
		if (!data) return
		foldersRequest++
		state.folders = state.folders.map((folder) => (folder.path === path ? data.workspace : folder))
		notify("Workspace renamed")
	}

	// it leaves the sidebar, its folder and chats stay: the chats are in no workspace now, and a new
	// chat about to start there moves to another
	async function removeFolder(path) {
		const ok = await guard(() => client.removeWorkspace(path))
		if (ok === null) return
		foldersRequest++
		state.folders = state.folders.filter((folder) => folder.path !== path)
		for (const session of state.sessions) if (session.workspace === path) session.workspace = null
		if (!state.sessionId && state.prefs.cwd === path) setCwd(latestFolder())
		notify("Workspace deleted")
	}

	// Typing filters the loaded rows, which is exact only while every session is loaded;
	// past a full page the host searches instead, and clearing the box reloads the list.
	function searchSessions(query) {
		if (query === listQuery) return
		if (!listQuery && !state.sessionsMore) return
		return refreshSessions({ query })
	}

	// only the newest request lands, so an older answer can't end its loading or replace its list
	let modelsRequest = 0
	async function refreshModels() {
		const own = ++modelsRequest
		state.modelsLoading = true
		const data = await guard(() => client.models())
		if (own !== modelsRequest) return
		state.modelsLoading = false
		if (data) {
			state.models = data.models
			state.modelErrors = data.errors ?? []
		}
	}

	function refreshTools() {
		toolsLoading = loadTools()
		return toolsLoading
	}

	// silent: an older daemon has no /tools route, and the list is optional
	async function loadTools() {
		try {
			state.tools = (await client.tools()).tools
		} catch {
			state.tools = []
		}
	}

	function closeStream() {
		stream?.close()
		stream = null
		streamTask = null
	}

	function resetWorkspace() {
		state.workspace = { open: false, maximized: false, tabs: [], active: null, view: null }
	}

	// Open tabs and panel visibility survive refreshes and session switches:
	// persisted per session (paths only — unsaved edits are not kept).
	let workspaceBySession = readJSON(keys.workspace, {})

	function persistWorkspace() {
		const sid = state.sessionId
		if (!sid) return
		const ws = state.workspace
		if (ws.tabs.length || ws.open) {
			workspaceBySession[sid] = {
				open: ws.open,
				maximized: ws.maximized,
				active: ws.active,
				view: ws.view ?? null,
				tabs: ws.tabs.map((t) => ({ kind: t.kind, path: t.path, diff: !!t.diff })),
			}
		} else {
			delete workspaceBySession[sid]
		}
		localStorage.setItem(keys.workspace, JSON.stringify(workspaceBySession))
	}

	function restoreWorkspace(sid) {
		const saved = workspaceBySession[sid]
		// corrupt storage must never break opening the session itself; tabs were
		// stored as plain paths before the diff flag existed
		const stored = (Array.isArray(saved?.tabs) ? saved.tabs : [])
			.map((tab) => (typeof tab === "string" ? { path: tab } : tab))
			.filter((tab) => tab && typeof tab.path === "string" && tab.path)
		if (!stored.length && !saved?.open) return
		const paths = stored.map((tab) => tab.path)
		// a narrow frame's panel covers the chat, so a chat opens on itself, with its tabs kept
		const open = !layout.narrow && (saved.open ?? true)
		state.workspace = {
			open,
			maximized: open && !!saved.maximized,
			view: ["files", "diff"].includes(saved.view) ? saved.view : null,
			tabs: stored.map(({ kind, path, diff }) =>
				kind === "subagent"
					? { kind, path, name: "Sub-agent" } // named once the thread is loaded
					: {
							kind: "editor",
							path,
							name: path.split(/[\\/]/).filter(Boolean).pop() ?? path,
							content: null,
							original: null,
							error: null,
							loading: false,
							dirty: false,
							diff: !!diff,
						},
			),
			active: saved.active == null ? null : paths.includes(saved.active) ? saved.active : (paths[0] ?? null),
		}
	}

	async function openSession(sid, { sending = [], config = null } = {}) {
		const own = ++opening
		closeStream()
		// a same-session reload (rewind) keeps the open file tabs as they are, and a chat
		// just created (`config`) keeps the ones opened before its first message
		const switching = state.sessionId !== sid && !config
		if (switching) resetWorkspace()
		swapQueue(sid)
		state.sessionId = sid
		if (switching) restoreWorkspace(sid)
		else if (config) persistWorkspace()
		// seed cwd/title from the session list so the header doesn't flash empty
		// while the full session loads; no session_id, so a list refresh doesn't take
		// the seed's display title for the session's own
		const listed = state.sessions.find((s) => s.session_id === sid)
		const known = listed ?? (config && { title: config.title, cwd: config.cwd })
		state.session = known
			? { title: known.title ?? state.titles[sid] ?? null, config: { cwd: known.cwd } }
			: null
		state.skills = []
		loadedSkillsFor = null
		state.conversation = initialConversation()
		// a chat just created knows its model, and a list row's when the host vouches for it;
		// anything else waits for the load
		state.conversation.model = config?.model ?? (options.listedModel ? listed?.model : null) ?? null
		lastRunEnd = null
		// a message sent before this session existed is still in flight: its bubble
		// stays up instead of blinking out while the transcript loads
		state.conversation.sending = sending
		state.loading = true
		const [info, catalog] = await Promise.all([
			guard(() => client.session(sid)),
			options.skillsEnabled && typeof client.skills === "function"
				? guard(() => client.skills(sid))
				: Promise.resolve({ skills: [] }),
		])
		if (state.sessionId !== sid || own !== opening) return
		// a chat that failed to load (gone, or not this user's) leaves a blank chat, not one
		// that can't send
		if (!info) return startNewChat()
		// Seed from the active branch, not a raw-log replay: the log also holds
		// rewind markers and abandoned rows, which must never enter the
		// transcript (a replayed rewind would trigger an endless reload loop).
		const seed = await guard(() => client.entries(sid))
		if (state.sessionId !== sid || own !== opening) return
		if (!seed) return startNewChat()
		if (seed.latest_seq > info.latest_seq) info.latest_seq = seed.latest_seq
		state.session = info
		// hydrate the restored active tab now that the session's cwd is known
		if (switching && state.workspace.open && state.workspace.active)
			selectFile(state.workspace.active)
		state.skills = catalog?.skills ?? []
		loadedSkillsFor = skillsKey()
		state.conversation.model = info.model
		state.conversation.reasoningEffort = info.reasoning_effort ?? null
		state.conversation.contextTokens = info.context_tokens ?? 0
		for (const entry of seed.entries) applyEvent(state.conversation, entry)
		const lastEnded = seed.entries.findLast((entry) => entry.type === "run_ended" && !entry.subagent_id)
		lastRunEnd = lastEnded?.reason ?? null
		syncSubagentTabs()
		// A trailing model_changed has no usage yet, so fall back to the selected
		// model's static limit from the session detail response.
		state.conversation.contextWindow ??= info.context_window ?? null
		state.prefs.lastSession = sid // restored on the next page load
		savePrefs()
		state.loading = false
		startStream(sid, seed.latest_seq)
		// a run that ran its course after the next waiting message was queued, while this chat
		// was closed or the page reloaded, still hands it a turn
		const next = state.queued[0]
		if (next && !state.conversation.running && ranItsCourse(lastRunEnd) && lastEnded.seq > next.afterSeq)
			void sendWaiting(next)
	}

	function startStream(sid, since) {
		const own = (stream = client.stream(sid, since))
		streamTask = (async () => {
			try {
				for await (const event of own) {
					if (stream !== own || state.sessionId !== sid) return
					handleEvent(sid, event)
					if (state.conversation.needsReload) {
						// a live rewind retracted rows: re-seed from the new branch
						await openSession(sid)
						return
					}
				}
			} catch (error) {
				if (stream === own) notify(error.message, "error")
			} finally {
				// a stream closed by a reload of this same chat must not end that reload's loading
				if (stream === own && state.sessionId === sid) state.loading = false
			}
		})()
	}

	function handleEvent(sid, event) {
		if (event.type === "title_changed") {
			if (state.session) state.session.title = event.title
			const listed = state.sessions.find((info) => info.session_id === sid)
			if (listed) listed.title = event.title
			return
		}
		applyEvent(state.conversation, event)
		// an error witnessed live shows in full, in the thread it belongs to
		if (event.type === "run_error" && event.seq > (state.session?.latest_seq ?? 0)) {
			const thread = event.subagent_id ? state.conversation.subagents[event.subagent_id] : state.conversation
			thread.liveErrorSeqs.push(event.seq)
		}
		if (event.subagent_id) return // a sub-agent's rows change nothing below
		if (event.type === "user_message") {
			// Match attachment messages, whose text is wrapped in content blocks.
			const blocks = Array.isArray(event.content) ? event.content : []
			const expandedText = Array.isArray(event.content)
				? blocks
						.filter((block) => block.type === "text")
						.map((block) => block.text)
						.join("")
				: event.content
			const text = skillCommand(event) ?? expandedText
			const attachmentIds = blocks
				.filter((block) => block.type === "attachment")
				.map((block) => block.id)
			// by name too: after a reload, /flow's echo can't name the File a message was sent as
			const steered = state.conversation.steering.findIndex(
				(item) =>
					item.text === text &&
					(sameFiles(item.attachmentIds, attachmentIds) ||
						sameFiles(attachmentNames(item.entry.content), attachmentNames(blocks))),
			)
			if (steered !== -1) state.conversation.steering.splice(steered, 1)
			rememberTitle(sid)
		}
		// the server discards steering it never consumed, and no echo will clear it; the
		// messages still waiting stay for the user to send or take back
		if (event.type === "run_ended" && event.reason !== "paused")
			state.conversation.steering = []
		if (event.type === "run_ended") lastRunEnd = event.reason
		// a run that ran its course hands the next waiting message a turn of its own
		if (
			event.type === "run_ended" &&
			ranItsCourse(event.reason) &&
			event.seq > (state.session?.latest_seq ?? 0)
		) {
			if (state.queued.length) void sendWaiting(state.queued[0])
		}
		// only a live run boundary is picker activity, not replayed history
		if (
			(event.type === "run_started" || event.type === "run_ended") &&
			event.seq > (state.session?.latest_seq ?? 0)
		) {
			let sessionState = "running"
			if (event.type === "run_ended") sessionState = event.reason === "paused" ? "paused" : "idle"
			recordRunBoundary(sid, sessionState)
		}
	}

	// A run boundary is the open session's newest activity: its row takes the new state
	// and the top of the picker. A session the picker doesn't list yet (the daemon lists
	// one from its first durable row) is fetched instead.
	function recordRunBoundary(sid, sessionState) {
		if (state.session) state.session.state = sessionState
		const row = state.sessions.find((info) => info.session_id === sid)
		if (!row) {
			refreshSessions()
			return
		}
		row.state = sessionState
		state.sessions = [row, ...state.sessions.filter((info) => info.session_id !== sid)]
	}

	// Reset to the blank "new chat" state, in the caller's folder or newChatCwd's.
	// No server call — send() creates it lazily.
	function startNewChat({ cwd = null } = {}) {
		const nextCwd = cwd ?? newChatCwd()
		closeStream()
		resetWorkspace()
		swapQueue(null)
		state.sessionId = null
		state.session = null
		state.loading = false // a session still opening is dropped
		state.skills = []
		state.conversation = initialConversation()
		loadedSkillsFor = null
		state.prefs.lastSession = null
		state.prefs.cwd = nextCwd
		savePrefs()
	}

	// a new chat keeps its folder; else the open chat's, and where the daemon keeps workspaces
	// only one of theirs: the open chat's, the last one used, else the latest
	function newChatCwd() {
		if (!state.sessionId && state.prefs.cwd) return state.prefs.cwd
		const listed = state.sessions.find((session) => session.session_id === state.sessionId)
		const open = state.session?.config?.cwd ?? listed?.cwd
		if (!state.folders) return open ?? state.prefs.cwd
		return [listed?.workspace, open, state.prefs.cwd].find(isFolder) ?? latestFolder()
	}

	async function newSession({ cwd = null, model = null, sending = [] } = {}) {
		const blank = state.conversation // the chat this one is created from
		await toolsLoading // the Default preset's picks need the tool list to build on
		const preset = activePreset()
		const picked = preset ?? defaultPreset()
		const config = {
			auto_approve: state.prefs.mode === "auto",
		}
		if (picked?.tools) config.tools = picked.tools
		if (picked?.extensionTools) config.extension_tools = picked.extensionTools
		if (preset) config.preset = preset.id // the chat keeps it, for the settings tab
		const prompt = preset?.prompt?.trim() ?? ""
		if (prompt && preset.promptMode === "replace") config.system_preamble = prompt
		const suffix = [preset?.promptMode === "append" ? prompt : "", state.prefs.customInstructions.trim()]
			.filter(Boolean)
			.join("\n\n")
		if (suffix) config.system_suffix = suffix
		const useCwd = cwd ?? state.prefs.cwd
		if (useCwd) config.cwd = useCwd
		const useModel = model ?? state.prefs.lastModel
		if (useModel) config.model = useModel
		const data = await guard(() => client.createSession(config), { rethrow: false })
		if (!data) return null
		const effort = state.prefs.lastEffort
		if (effort) {
			await guard(() =>
				client.setModel(data.session_id, {
					// the model the chat was made with: a host may refuse one it no longer offers
					model: data.config.model ?? useModel,
					reasoning_effort: effort === "default" ? null : effort,
				}),
			)
		}
		await refreshSessions()
		// a user who opened another chat meanwhile stays there
		if (state.conversation === blank) await openSession(data.session_id, { sending, config: data.config })
		return data.session_id
	}

	// state.skills belongs to a live session, or to the folder a new chat would use
	function skillsKey() {
		return state.sessionId ? `session:${state.sessionId}` : `cwd:${state.prefs.cwd ?? ""}`
	}

	// `force` refetches after a skill is written or deleted.
	async function loadSkills({ force = false } = {}) {
		if (!options.skillsEnabled) return
		const sid = state.sessionId
		const cwd = state.prefs.cwd
		// a live session reports what it can invoke; before one exists, preview the folder
		const fetcher = sid ? client.skills : client.previewSkills
		if (typeof fetcher !== "function") return
		const fetchSkills = sid
			? () => client.skills(sid)
			: () => client.previewSkills(cwd ? { cwd } : {})
		const key = skillsKey()
		if (force) loadedSkillsFor = null
		else if (loadedSkillsFor === key) return
		const pending =
			!force && loadingSkills?.key === key ? loadingSkills.promise : guard(fetchSkills)
		loadingSkills = { key, promise: pending }
		try {
			const catalog = await pending
			// a forced refetch supersedes an older request for the same key
			if (loadingSkills?.promise === pending && skillsKey() === key && catalog) {
				state.skills = catalog.skills ?? []
				loadedSkillsFor = key
			}
		} finally {
			if (loadingSkills?.promise === pending) loadingSkills = null
			// the session or folder changed while this was in flight; load the new one
			if (skillsKey() !== key) void loadSkills()
		}
	}

	// what the composer says of its model when the host runs only the models it lists
	// (options.onlyListedModels) and this one isn't among them
	function modelWarning() {
		const model = state.conversation.model ?? (state.loading ? null : state.prefs.lastModel)
		if (!options.onlyListedModels || !model || !state.models.length) return null
		if (state.models.some((item) => item.name === model)) return null
		return `${modelTitle(model, state.models)} isn't available to you. Pick a different model.`
	}

	async function send(text, attachments = []) {
		const message = text.trim()
		if (!message && !attachments.length) return false
		// uploads and @-mentions stage through separate endpoints that each cap at
		// MAX_ATTACHMENTS; only their sum rides the run, so check it before staging
		// anything — otherwise both succeed and the run is rejected as oversized.
		if (attachments.length > options.maxAttachments) {
			notify(`A message can carry at most ${options.maxAttachments} attachments.`, "error")
			return false
		}
		// a paused run refuses every message until its approval is answered, so say that
		// here instead of sending one and handing the text back with an error
		if (state.conversation.pendingApproval) {
			notify("Answer the approval before sending another message.", "error")
			return false
		}
		// A run going, or about to start with a message still on its way, holds the next
		// message in the queue until it ends, or until the user steers it in. Its files go
		// up first, so the queue holds only ids and outlives a reload.
		const busy = () => state.conversation.running || state.conversation.sending.length > 0
		if (!state.sessionId || !busy()) return sendNow(message, attachments)
		const sid = state.sessionId
		const afterSeq = state.conversation.latestSeq
		const staged = await stageAttachments(sid, attachments)
		if (!staged) return false
		if (state.sessionId !== sid) {
			// the user moved on while the files went up: it waits with its own session
			const held = { message, attachments: staged.attachments, afterSeq }
			heldBySession.set(sid, [...(heldBySession.get(sid) ?? []), held])
			return true
		}
		// the run may have ended while the files went up: if on its own, the message goes now,
		// unless others wait ahead of it; after a stop, it waits with them
		if (!busy() && !state.queued.length && ranItsCourse(lastRunEnd))
			return sendNow(message, staged.attachments)
		state.queued.push(queueItem(message, staged.attachments, afterSeq))
		return true
	}

	// Opens the next turn, its bubble up before the first round trip: creating the
	// session, searching memory and reaching the daemon happen behind it.
	async function sendNow(message, attachments) {
		const pending = { key: `sending:${++sendCount}`, entry: userEntry(message, attachments) }
		state.conversation.sending.push(pending)
		const sent = await deliver(message, attachments, pending, null)
		// nothing was sent, so nothing will echo it back: take it down again
		if (!sent) unsend(pending)
		return sent
	}

	// the queue's button: steer a waiting message into the running turn, or send it now
	// when no run is going (a stopped or failed run leaves its queue waiting)
	async function sendQueued(item) {
		if (!state.queued.includes(item)) return
		if (state.conversation.pendingApproval) {
			notify("Answer the approval before sending another message.", "error")
			return
		}
		if (!state.conversation.running) return sendWaiting(item)
		// its bubble goes below the turn at once; one that fails to send waits again
		const sid = state.sessionId
		const at = state.queued.indexOf(item)
		unqueue(item)
		const steered = steeringBubble(item.message, item.attachments)
		state.conversation.steering.push(steered)
		const pending = { key: `sending:${++sendCount}`, entry: steered.entry }
		if (await deliver(item.message, item.attachments, pending, steered)) return
		unsteer(steered)
		requeue(sid, item, at)
	}

	// a waiting message opens a turn of its own; one that fails to send waits again
	async function sendWaiting(item) {
		const sid = state.sessionId
		const at = state.queued.indexOf(item)
		unqueue(item)
		if (!(await sendNow(item.message, item.attachments))) requeue(sid, item, at)
	}

	// back where it waited, in its own session's queue even if another is open now
	function requeue(sid, item, at) {
		if (state.sessionId === sid) state.queued.splice(at, 0, item)
		else heldBySession.set(sid, (heldBySession.get(sid) ?? []).toSpliced(at, 0, waitingRecord(item)))
	}

	// A waiting message taken back drops what was staged for it; the server keeps any file
	// an earlier message holds.
	function removeQueued(item) {
		if (!state.queued.includes(item)) return
		unqueue(item)
		const ids = item.attachments.map((attachment) => attachment.id)
		if (ids.length) void client.cleanupAttachments(state.sessionId, ids).catch(() => {})
	}

	// A row of the composer's queue: a message waiting for the run to end. `afterSeq` is how
	// far the chat had got when it was queued; only a run that ends past it hands it a turn.
	function queueItem(message, attachments, afterSeq) {
		return {
			key: `queued:${++queueCount}`,
			message,
			attachments,
			afterSeq,
			label: message || `${attachments.length} attachment(s)`,
		}
	}

	// A steered message's bubble, until the server's echo, matched on `text` and
	// `attachmentIds`, shows the turn took it.
	function steeringBubble(message, attachments, attachmentIds = []) {
		return {
			key: `steering:${++sendCount}`,
			entry: userEntry(message, attachments),
			text: normalizeSkillCommand(message) ?? message,
			attachmentIds,
		}
	}

	// what a waiting message keeps while its session is closed, or across a reload
	function waitingRecord({ message, attachments, afterSeq }) {
		return { message, attachments, afterSeq }
	}

	// a session's waiting messages wait with it while another is open; steering is the
	// server's, and the transcript shows it once the turn takes it
	function swapQueue(sid) {
		if (state.sessionId && state.queued.length) heldBySession.set(state.sessionId, state.queued.map(waitingRecord))
		state.queued = (heldBySession.get(sid) ?? []).map((held) => queueItem(held.message, held.attachments, held.afterSeq))
		heldBySession.delete(sid)
	}

	function unqueue(item) {
		const at = item ? state.queued.indexOf(item) : -1
		if (at >= 0) state.queued.splice(at, 1)
	}

	function unsteer(steered) {
		const at = state.conversation.steering.indexOf(steered)
		if (at >= 0) state.conversation.steering.splice(at, 1)
	}

	function unsend(pending) {
		const at = state.conversation.sending.indexOf(pending)
		if (at >= 0) state.conversation.sending.splice(at, 1)
	}

	// what a sent message looks like until the server has one of its own
	function userEntry(message, attachments) {
		const blocks = attachments.map((item) => ({
			type: "attachment",
			id: item.id ?? item.key,
			name: item.name,
			kind: item.kind,
		}))
		return { type: "user_message", content: [{ type: "text", text: message }, ...blocks], ts: Date.now() / 1000 }
	}

	// the round trips the bubble hides: the session, the attachments, the run
	async function deliver(message, attachments, pending, steered) {
		let sid = state.sessionId
		const created = !sid
		if (created) {
			if (options.requireCwd && !state.prefs.cwd) {
				notify("Choose a project folder before sending a message.", "error")
				return false
			}
			// only from the same blank chat: one opened since makes a chat of its own
			if (creating?.blank !== state.conversation)
				creating = { blank: state.conversation, session: newSession({ sending: state.conversation.sending }) }
			const own = creating
			try {
				// the chat created for it, even if the user has opened another since
				sid = await own.session
				if (!sid) return false
			} finally {
				if (creating === own) creating = null
			}
		}
		const staged = await stageAttachments(sid, attachments)
		if (!staged) return false
		const attachmentIds = staged.attachments.map((item) => item.id)
		let admitted = false
		try {
			// the echo that clears a steered message is matched on the attachments that rode
			// with it, and the turn can consume it before this call answers
			if (steered) steered.attachmentIds = attachmentIds
			const seen = state.conversation.entries.length
			const result = await guard(() => client.run(sid, message, attachmentIds))
			if (!result) return false
			admitted = true
			if (state.sessionId !== sid) {
				// the user left the chat this message created before it ran: list it for them
				if (created) void refreshSessions()
				return true
			}
			// the server decides which it was; a client that guessed wrong moves it now
			if (result.status === "steered") {
				// it waits below the turn, unless the turn took it while this call answered
				const unechoed = state.conversation.sending.includes(pending)
				unsend(pending)
				if (!steered && unechoed)
					state.conversation.steering.push(steeringBubble(message, staged.attachments, attachmentIds))
			} else if (steered) {
				// it opened a turn of its own, so it needs its bubble — unless the echo
				// arrived while this call was answering and drew one already
				unsteer(steered)
				const echoed = state.conversation.entries
					.slice(seen)
					.some((entry) => entry.type === "user_message")
				if (!echoed) state.conversation.sending.push(pending)
			}
			return true
		} finally {
			if (!admitted && staged.created.length) {
				// A claimed attachment is retained if the run reached the daemon but its
				// response was lost; only genuinely unclaimed staging data is removed.
				await client.cleanupAttachments(sid, staged.created).catch(() => {})
			}
		}
	}

	// Uploads and @-mentions staged on the server, so a message names every attachment by
	// id: { attachments: [{ id, name, kind }], created: ids staged by this call }, or null
	// when one failed (the guard has said why, and nothing staged here is left behind).
	async function stageAttachments(sid, attachments) {
		const uploads = attachments.filter((item) => item.file && !item.id).map((item) => item.file)
		const mentionPaths = attachments.filter((item) => item.mentionPath).map((item) => item.mentionPath)
		// independent sources — resolve concurrently rather than paying two round trips
		const [uploaded, attached] = await Promise.all([
			uploads.length ? guard(() => client.uploadAttachments(sid, uploads)) : null,
			mentionPaths.length ? guard(() => client.attachFiles(sid, mentionPaths)) : null,
		])
		const created = [uploaded, attached].flatMap((resolved) => resolved?.attachments ?? [])
		if ((uploads.length && !uploaded) || (mentionPaths.length && !attached)) {
			if (created.length) await client.cleanupAttachments(sid, created.map((item) => item.id)).catch(() => {})
			return null
		}
		return {
			attachments: [...attachments.filter((item) => item.id), ...created].map(({ id, name, kind }) => ({ id, name, kind })),
			created: created.map((item) => item.id),
		}
	}

	// Approval answers: "Approve" | "Deny" | free text. Resume fires once every
	// undecided call in the batch has an answer (the server validates exactness).
	// A deny stops the run, so it settles the batch: undecided calls deny with it
	// (explicit answers stand, matching the server's approve-then-halt order).
	async function answerApproval(callId, answer, pending = approvalToAnswer(state.conversation)) {
		if (!pending) return
		pending.answers[callId] = answer
		if (answer === "Deny") {
			for (const call of pending.calls) {
				if (!(call.id in pending.answers)) pending.answers[call.id] = "Deny"
			}
		}
		const undecided = pending.calls.filter((c) => !(c.id in pending.answers))
		if (undecided.length > 0) return
		const answers = { ...pending.answers }
		const result = await guard(() => client.resume(state.sessionId, pending.seq, answers))
		// a failed resume must not strand the batch as "Answered" — reopen it
		if (result === null) pending.answers = {}
	}

	async function abort() {
		if (!state.sessionId) return
		// steering dies with the run; waiting messages stay for the user
		state.conversation.steering = []
		await guard(() => client.abort(state.sessionId))
	}

	async function cancelPending() {
		if (!state.sessionId) return
		await guard(() => client.cancelPending(state.sessionId))
	}

	async function compact() {
		if (!state.sessionId) return
		// a compaction takes no steering, and its run starts before the compaction does; while
		// a run goes the server refuses one, so nothing changes until it says so
		const conversation = state.conversation
		if (!conversation.running) conversation.compacting = "manual"
		const result = await guard(() => client.compact(state.sessionId))
		if (result === null && conversation.compacting === "manual") conversation.compacting = false
	}

	async function reloadExtensions() {
		const info = await guard(() => client.reloadExtensions())
		if (info === null) return
		await refreshTools() // a reload can add or drop extension tools
		const names = info.extensions.map((extension) => extension.name)
		const errors = info.diagnostics.filter((diagnostic) => diagnostic.severity === "error")
		if (errors.length) notify(`Extension error: ${errors[0].message}`, "error")
		else notify(names.length ? `Extensions reloaded: ${names.join(", ")}` : "Extensions reloaded: none loaded")
	}

	// Rewind to just before a user message: everything after it leaves the
	// active branch, and its text lands in the composer draft for rephrasing.
	async function rewindToMessage(entry) {
		if (!capabilities.rewind) return null
		// the confirm dialog may outlive a session switch — this entry's seqs
		// only mean anything in the conversation it came from
		if (!state.conversation.entries.includes(entry)) return null
		// branch from the entry before the message's run_started; the message's
		// parent chain makes parent_seq the correct anchor
		const target = (entry.parent_seq ?? 1) - 1
		const sid = state.sessionId
		const ok = await guard(() => client.rewind(sid, Math.max(target, 0)))
		// the draft belongs in this chat's box, not one the user opened meanwhile
		if (ok === null || state.sessionId !== sid) return null
		const content = Array.isArray(entry.content) ? entry.content : []
		const expandedText = Array.isArray(entry.content)
			? content.filter((block) => block.type === "text").map((block) => block.text).join("")
			: entry.content
		const text = skillCommand(entry) ?? expandedText
		const attachments = content
			.filter((block) => block.type === "attachment")
			.map((block) => ({ ...block }))
		setDraft({ text, attachments })
		return text
	}

	async function rewindLastUserMessage() {
		// a message steered into a run has no rewind point, so the run's own message stands in
		const steered = state.conversation.steeredSeqs
		const last = [...state.conversation.entries]
			.reverse()
			.find((e) => e.type === "user_message" && !steered.includes(e.seq))
		if (!last) return null
		return rewindToMessage(last)
	}

	// One-way channel into the composer (it watches and consumes this).
	function setDraft(draft) {
		state.draft = draft
	}

	// Editor selections referenced in the next message as path:lines, not pasted text.
	function addCodeRef(path, start, end) {
		const cwd = state.session?.config?.cwd
		const rel = cwd && path.startsWith(cwd + "/") ? path.slice(cwd.length + 1) : path
		// by rel: a rewound token comes back relative, the editor sends the full path
		if (state.codeRefs.some((r) => r.rel === rel && r.start === start && r.end === end)) return
		state.codeRefs.push({ path, rel, start, end })
	}

	function removeCodeRef(index) {
		state.codeRefs.splice(index, 1)
	}

	// Drop the refs a message carried, or every one after a session switch.
	function clearCodeRefs(sent = null) {
		state.codeRefs = sent ? state.codeRefs.filter((ref) => !sent.includes(ref)) : []
	}

	// Thread selections quoted under the next message, as the text itself.
	function addQuote(text) {
		if (!state.quotes.includes(text)) state.quotes.push(text)
	}

	function removeQuote(index) {
		state.quotes.splice(index, 1)
	}

	function clearQuotes(sent = null) {
		state.quotes = sent ? state.quotes.filter((quote) => !sent.includes(quote)) : []
	}

	async function selectModel(model) {
		const sid = state.sessionId
		if (!sid) {
			state.prefs.lastModel = model
			return savePrefs()
		}
		const data = await guard(() =>
			client.setModel(sid, {
				model,
				reasoning_effort:
					state.prefs.lastEffort && state.prefs.lastEffort !== "default" ? state.prefs.lastEffort : null,
			}),
		)
		// a chat refuses a change while it runs: only one it took becomes the default
		if (!data) return
		state.prefs.lastModel = model
		savePrefs()
		// the list's copy is what this chat shows while it reopens
		const listed = state.sessions.find((s) => s.session_id === sid)
		if (listed) listed.model = data.model
		if (state.sessionId !== sid) return // the user moved to another chat meanwhile
		state.conversation.model = data.model
		state.conversation.contextWindow = data.context_window ?? null
		if (state.session) {
			state.session.model = data.model
			state.session.context_window = data.context_window ?? null
			state.session.supports_images = data.supports_images
		}
	}

	// a model the host renamed stays the one a new chat starts with
	function renamedModel(from, to) {
		if (state.prefs.lastModel !== from) return
		state.prefs.lastModel = to
		savePrefs()
	}

	async function selectEffort(effort) {
		const sid = state.sessionId
		if (!sid) {
			state.prefs.lastEffort = effort
			return savePrefs()
		}
		const model = state.conversation.model ?? state.session?.model
		if (!model) return
		const data = await guard(() =>
			client.setModel(sid, {
				model,
				reasoning_effort: effort === "default" ? null : effort,
			}),
		)
		// a chat refuses a change while it runs: only one it took becomes the default
		if (!data) return
		state.prefs.lastEffort = effort
		savePrefs()
		if (state.sessionId !== sid) return // the user moved to another chat meanwhile
		state.conversation.reasoningEffort = effort === "default" ? null : effort
	}

	// Approval mode: remembered for new chats, and applied to the current session
	// immediately — mid-run flips take effect at the next tool gate.
	async function setMode(mode) {
		state.prefs.mode = mode
		savePrefs()
		const sid = state.sessionId
		if (!sid) return
		const data = await guard(() => client.patchConfig(sid, { auto_approve: mode === "auto" }))
		// the server never switched, or the user moved to another chat meanwhile: don't act on it here
		if (!data || state.sessionId !== sid) return
		if (state.session) state.session.config = data.config
		if (mode !== "auto") return
		// the batches already waiting at the gate are covered by the new mode: approve
		// whatever the user hasn't decided yet (their explicit answers stand)
		for (const pending of waitingApprovals(state.conversation)) {
			for (const call of pending.calls) {
				if (state.sessionId !== sid) return
				if (!(call.id in pending.answers)) await answerApproval(call.id, "Approve", pending)
			}
		}
	}

	// The working directory new chats are created in (until changed again).
	function setCwd(path) {
		// pre-session tabs belong to the previous pick: close them with it
		if (!state.sessionId && state.prefs.cwd !== path) resetWorkspace()
		state.prefs.cwd = path
		if (!state.sessionId) {
			state.skills = []
			loadedSkillsFor = null
		}
		savePrefs()
	}

	// Open a file in the workspace panel, refetching unless unsaved edits exist.
	// The explorer browses one cwd: the session's, or the picked one before the
	// first message. Null while a session is still loading, so nothing fetches
	// against the wrong directory in that window.
	function explorerCwd() {
		if (state.sessionId) return state.session?.config?.cwd ?? null
		return state.prefs.cwd ?? null
	}

	async function openFile(path) {
		const cwd = explorerCwd()
		const stale = () => explorerCwd() !== cwd // a session or cwd switch mid-flight
		if (!cwd || typeof client.readFile !== "function") return
		const ws = state.workspace
		let tab = ws.tabs.find((t) => t.path === path)
		if (!tab) {
			ws.tabs.push({
				kind: "editor",
				path,
				name: path.split(/[\\/]/).filter(Boolean).pop() ?? path,
				content: null,
				original: null,
				error: null,
				loading: false,
				dirty: false,
				diff: false,
			})
			tab = ws.tabs[ws.tabs.length - 1]
		}
		tab.diff = false
		ws.active = path
		ws.open = true
		persistWorkspace()
		if (tab.dirty) return
		tab.loading = true
		try {
			const data = await client.readFile(cwd, path)
			if (stale()) return
			tab.content = data.content
			tab.error = null
		} catch (error) {
			if (stale()) return
			tab.error = String(error?.message ?? error)
			tab.content = null
		} finally {
			tab.loading = false
		}
	}

	// Diff twin of openFile: the tab shows the file's uncommitted changes, with
	// HEAD as the original side; the working-tree content stays the editable
	// (and savable) side.
	async function openDiffFile(path) {
		const cwd = explorerCwd()
		const stale = () => explorerCwd() !== cwd
		if (!cwd) return
		// hosts with an older client surface fall back to the plain viewer
		if (typeof client.gitFileDiff !== "function") return openFile(path)
		const ws = state.workspace
		let tab = ws.tabs.find((t) => t.path === path)
		if (!tab) {
			ws.tabs.push({
				kind: "editor",
				path,
				name: path.split(/[\\/]/).filter(Boolean).pop() ?? path,
				content: null,
				original: null,
				error: null,
				loading: false,
				dirty: false,
				diff: true,
			})
			tab = ws.tabs[ws.tabs.length - 1]
		}
		tab.diff = true
		ws.active = path
		ws.open = true
		persistWorkspace()
		tab.loading = true
		// a 400 means the file lies outside the repo (or there is none): the
		// session's own recorded changes still diff it, so TurnFiles clicks work
		const fetchDiff = async () => {
			try {
				return await client.gitFileDiff(cwd, path)
			} catch (error) {
				const outside = error instanceof FlowAPIError && error.status === 400
				if (!outside || !state.sessionId || typeof client.fileDiff !== "function") throw error
				return client.fileDiff(state.sessionId, path)
			}
		}
		try {
			const data = await fetchDiff()
			if (stale()) return
			// an empty original means the file is new or untracked; the tab stays in
			// the diff view but renders as a plain file (nothing to compare against)
			tab.original = data.original
			if (!tab.dirty) tab.content = data.modified
			tab.error = null
		} catch (error) {
			if (stale()) return
			tab.error = String(error?.message ?? error)
			if (!tab.dirty) tab.content = null
		} finally {
			tab.loading = false
		}
	}

	// One directory level for the explorer; null on failure (toast already shown).
	async function listFiles(path = "") {
		const cwd = explorerCwd()
		if (!cwd || typeof client.listFiles !== "function") return null
		return guard(() => client.listFiles(cwd, path))
	}

	async function searchFiles(query) {
		const cwd = explorerCwd()
		if (!cwd || typeof client.searchFiles !== "function") return null
		return guard(() => client.searchFiles(cwd, query))
	}

	// the diff bar polls this, so failures stay silent instead of toasting
	async function gitChanges() {
		const cwd = explorerCwd()
		if (!cwd || typeof client.gitChanges !== "function") return null
		try {
			return await client.gitChanges(cwd)
		} catch {
			return null
		}
	}

	// a new chat's branch line, which a failure leaves out as quietly
	async function gitBranch() {
		const cwd = explorerCwd()
		if (!cwd || typeof client.gitBranch !== "function") return null
		try {
			return await client.gitBranch(cwd)
		} catch {
			return null
		}
	}

	// the "+ → Files" view: panel open with no active tab, explorer as the focus
	function showFilesView() {
		state.workspace.open = true
		state.workspace.view = "files"
		state.workspace.active = null
		state.workspace.focusSearch = true // once, for the files bar; never saved
		persistWorkspace()
	}

	function showDiffView() {
		state.workspace.open = true
		state.workspace.view = "diff"
		state.workspace.active = null
		persistWorkspace()
	}

	// closing the transient Files tab: back to a file if one is open, else the picker
	function closeFilesView() {
		const ws = state.workspace
		ws.view = null
		if (ws.tabs.length) return selectFile(ws.tabs[0].path)
		persistWorkspace()
	}

	// Tab switches only activate — never refetch — so unsaved edits survive.
	// A restored tab has no content yet and hydrates on first activation.
	function selectFile(path) {
		const tab = state.workspace.tabs.find((t) => t.path === path)
		if (!tab) return
		state.workspace.active = path
		persistWorkspace()
		if (tab.kind === "editor" && tab.content == null && !tab.loading && !tab.error)
			void (tab.diff ? openDiffFile(path) : openFile(path))
	}

	// Open a sub-agent's thread in the workspace panel, beside the file tabs.
	function openSubagent(id) {
		const ws = state.workspace
		if (!ws.tabs.some((t) => t.path === id)) {
			const name = subagentTabName(id) ?? "Sub-agent"
			ws.tabs.push({ kind: "subagent", path: id, name })
		}
		ws.active = id
		ws.open = true
		persistWorkspace()
	}

	// a sub-agent tab is named by the loaded thread; one whose child left the branch closes
	function syncSubagentTabs() {
		for (const tab of [...state.workspace.tabs]) {
			if (tab.kind !== "subagent") continue
			const name = subagentTabName(tab.path)
			if (name == null) closeFile(tab.path)
			else tab.name = name
		}
	}

	// the tab reads like the step row; null once the call left the branch
	function subagentTabName(id) {
		const title = subagentTitle(state.conversation, id)
		return title == null ? null : `Sub-agent: ${title}`
	}

	async function saveFile(path, content) {
		const cwd = explorerCwd()
		const stale = () => explorerCwd() !== cwd
		const tab = state.workspace.tabs.find((t) => t.path === path)
		if (!cwd || !tab) return false
		// hosts with an older client surface only have the session-scoped save
		const write =
			typeof client.writeFsFile === "function"
				? () => client.writeFsFile(cwd, path, content)
				: state.sessionId && typeof client.writeFile === "function"
					? () => client.writeFile(state.sessionId, path, content)
					: null
		if (!write) return false
		const data = await guard(write)
		if (!data || stale()) return false
		// dirty is the editor's call: only it knows of keys typed while this was in flight
		tab.content = content
		tab.error = null
		return true
	}

	function markFileDirty(path, dirty) {
		const tab = state.workspace.tabs.find((t) => t.path === path)
		if (tab) tab.dirty = dirty
	}

	function closeFile(path) {
		const ws = state.workspace
		const index = ws.tabs.findIndex((t) => t.path === path)
		if (index === -1) return
		ws.tabs.splice(index, 1)
		if (ws.active === path) {
			ws.active = ws.tabs[Math.min(index, ws.tabs.length - 1)]?.path ?? null
			// a tab restored after a reload loads its file when it first comes forward
			if (ws.active) selectFile(ws.active)
		}
		if (!ws.tabs.length) {
			ws.open = false
			ws.maximized = false // a maximized panel must not outlive its last tab
			ws.view = null
		}
		persistWorkspace()
	}

	function setWorkspaceOpen(open) {
		state.workspace.open = open
		if (!open) {
			state.workspace.maximized = false
			state.workspace.view = null // reopening with no tabs lands on the view picker
		} else {
			// resume the last open file; selectFile also hydrates a restored tab
			const target = state.workspace.active ?? state.workspace.tabs[0]?.path
			if (target) return selectFile(target)
		}
		persistWorkspace()
	}

	function toggleWorkspaceMaximized() {
		state.workspace.maximized = !state.workspace.maximized
		persistWorkspace()
	}

	function setWorkspaceWidth(width) {
		state.prefs.workspaceWidth = width
		savePrefs()
	}

	function setExplorerWidth(width) {
		state.prefs.explorerWidth = width
		savePrefs()
	}

	function setSidebarOpen(open) {
		state.sidebarOpen = open
		if (layout.narrow) return
		state.prefs.sidebarOpen = open
		savePrefs()
	}

	function setSidebarWidth(width) {
		state.prefs.sidebarWidth = width
		savePrefs()
	}

	function setFolderOpen(cwd, open) {
		const others = state.prefs.openFolders.filter((path) => path !== cwd)
		state.prefs.openFolders = open ? [...others, cwd] : others
		savePrefs()
	}

	// any of sidebarGroup, sidebarOrder, chatOrder and folderOrder
	function setSidebarView(view) {
		Object.assign(state.prefs, view)
		savePrefs()
	}

	function setCustomInstructions(text) {
		state.prefs.customInstructions = text
		savePrefs()
	}

	// to the hundredth: stepping 15.01 by 1 would otherwise land on 16.009999999999998
	function setChatFontSize(px) {
		const size = Math.min(CHAT_FONT_SIZE.max, Math.max(CHAT_FONT_SIZE.min, px))
		state.prefs.chatFontSize = Math.round(size * 100) / 100
		savePrefs()
	}

	function setChatFontWeight(weight) {
		state.prefs.chatFontWeight = weight
		savePrefs()
	}

	function setSettingsOpen(open, tab = null) {
		if (tab) state.settingsTab = tab
		state.settingsOpen = open
	}

	// "Create a preset": settings, on a blank one; the presets tab takes the ask once, as it opens
	let newPresetAsked = false
	function createPreset() {
		newPresetAsked = true
		setSettingsOpen(true, "presets")
	}
	function takeNewPreset() {
		const asked = newPresetAsked
		newPresetAsked = false
		return asked
	}

	function setTranscriptOpen(open) {
		state.transcriptOpen = open
	}

	function savePresets() {
		localStorage.setItem(keys.presets, JSON.stringify(state.presets))
		queueSettings()
	}

	function activePreset() {
		return state.presets.find((p) => p.id === state.prefs.activePreset) ?? null
	}

	// create (no id) or update; returns the id
	function savePreset(preset) {
		// randomUUID needs a secure context, which a LAN address over plain http is not
		const id = preset.id ?? crypto.randomUUID?.() ?? `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`
		const row = { ...preset, id }
		const index = state.presets.findIndex((p) => p.id === id)
		if (index === -1) state.presets.push(row)
		else state.presets[index] = row
		savePresets()
		return id
	}

	function deletePreset(id) {
		state.presets = state.presets.filter((p) => p.id !== id)
		savePresets()
		if (state.prefs.activePreset === id) setActivePreset(null)
	}

	function setActivePreset(id) {
		state.prefs.activePreset = id
		savePrefs()
	}

	// the Default preset: the daemon's core tools plus what settings ticked on top of them,
	// or null when the daemon's own defaults apply (nothing ticked, or no tool list to build on)
	function defaultPreset() {
		const picked = state.prefs.defaultPreset
		if (!picked || !state.tools.length) return null
		return { tools: [...coreNames(), ...extras(picked.tools)], extensionTools: [...picked.extensionTools] }
	}

	// keeps only what sits on top of the core tools, so a core tool added later is on too
	function saveDefaultPreset({ tools, extensionTools }) {
		state.prefs.defaultPreset = { tools: extras(tools), extensionTools }
		savePrefs()
	}

	const coreNames = () => state.tools.filter((t) => !t.extension && !t.bundled).map((t) => t.name)
	const extras = (tools) => tools.filter((name) => !coreNames().includes(name))

	async function renameSession(sid, title) {
		const data = await guard(() => client.patchConfig(sid, { title }))
		if (!data) return
		const listed = state.sessions.find((info) => info.session_id === sid)
		if (listed) listed.title = data.config.title
		if (state.sessionId === sid && state.session) state.session.title = data.config.title
		notify("Chat renamed")
	}

	async function deleteSession(sid) {
		const ok = await guard(() => client.deleteSession(sid))
		if (ok === null) return // running (409) or gone — the toast already said so
		state.sessions = state.sessions.filter((s) => s.session_id !== sid)
		if (state.titles[sid]) {
			delete state.titles[sid]
			localStorage.setItem(keys.titles, JSON.stringify(state.titles))
		}
		if (workspaceBySession[sid]) {
			delete workspaceBySession[sid]
			localStorage.setItem(keys.workspace, JSON.stringify(workspaceBySession))
		}
		if (state.sessionId === sid) startNewChat()
		heldBySession.delete(sid)
		notify("Chat deleted")
	}

	// Pick a cwd via the daemon's native folder dialog; null = cancelled or unavailable.
	async function pickFolder() {
		try {
			const data = await client.fsPick()
			return data.path
		} catch (error) {
			if (error instanceof FlowAPIError && error.status === 501)
				notify("No folder dialog on this host — use /cwd <path> instead.", "error")
			else notify(error.message, "error")
			return null
		}
	}

	// Object URL for a stored image attachment, null when the host keeps none or
	// the file is gone (the badge falls back to the filename); the caller revokes it.
	async function attachmentPreview(sid, attachmentId) {
		if (typeof client.attachmentBlob !== "function") return null
		try {
			return URL.createObjectURL(await client.attachmentBlob(sid, attachmentId))
		} catch {
			return null
		}
	}

	function detach() {
		closeStream()
	}

	if (typeof client.settings === "function") {
		if (options.colorScheme) watch(options.colorScheme.colorScheme, queueSettings)
		void loadSettings()
	}

	return {
		state,
		client,
		capabilities,
		options,
		// Optional host staging before a session exists; the daemon uploads on send.
		prepareAttachment: client.prepareAttachment?.bind(client),
		discardAttachments: client.discardAttachments?.bind(client),
		refreshSessions,
		loadMoreSessions,
		searchSessions,
		refreshModels,
		refreshTools,
		openSession,
		startNewChat,
		newSession,
		loadSkills,
		modelWarning,
		send,
		sendQueued,
		removeQueued,
		answerApproval,
		abort,
		cancelPending,
		compact,
		reloadExtensions,
		rewindToMessage,
		rewindLastUserMessage,
		setDraft,
		addCodeRef,
		removeCodeRef,
		clearCodeRefs,
		addQuote,
		removeQuote,
		clearQuotes,
		selectModel,
		renamedModel,
		selectEffort,
		setMode,
		setCwd,
		openFile,
		openDiffFile,
		explorerCwd,
		listFiles,
		searchFiles,
		gitChanges,
		gitBranch,
		selectFile,
		openSubagent,
		showFilesView,
		showDiffView,
		closeFilesView,
		saveFile,
		markFileDirty,
		closeFile,
		setWorkspaceOpen,
		toggleWorkspaceMaximized,
		setWorkspaceWidth,
		setExplorerWidth,
		setSidebarOpen,
		setSidebarWidth,
		setFolderOpen,
		setSidebarView,
		setCustomInstructions,
		setChatFontSize,
		setChatFontWeight,
		setSettingsOpen,
		setTranscriptOpen,
		activePreset,
		savePreset,
		deletePreset,
		setActivePreset,
		createPreset,
		takeNewPreset,
		defaultPreset,
		saveDefaultPreset,
		renameSession,
		deleteSession,
		folderName,
		addFolder,
		renameFolder,
		removeFolder,
		pickFolder,
		attachmentPreview,
		sessionTitle,
		notify,
		detach,
	}
}
