import { reactive } from "vue"

import { FlowAPIError } from "./client.js"
import {
	applyEvent,
	conversationTitle,
	initialConversation,
	normalizeSkillCommand,
	skillCommand,
} from "./transcript.js"

const PREFS_KEY = "flow.ui.prefs"
const TITLES_KEY = "flow.ui.titles"
const SESSION_PRESETS_KEY = "flow.ui.sessionPresets"
const WORKSPACE_KEY = "flow.ui.workspace"
const PRESETS_KEY = "flow.ui.presets"

function sameArray(left, right) {
	return left.length === right.length && left.every((value, index) => value === right[index])
}

function readJSON(key, fallback) {
	try {
		return JSON.parse(localStorage.getItem(key)) ?? fallback
	} catch {
		return fallback
	}
}

// One store per connected daemon. `client` implements the DaemonClient surface;
// Flow's Frappe shell passes a proxy-backed client instead.
export function createFlowStore(client) {
	// theme lives in frappe-ui's useColorScheme (localStorage "theme"), not here
	const prefs = {
		mode: "ask", // "ask" | "auto" — applied at session create
		customInstructions: "", // sent as system_suffix at session create
		activePreset: null, // id of the agent preset applied to new chats
		lastModel: null,
		lastEffort: null,
		cwd: null,
		sidebarOpen: true,
		sidebarWidth: 288,
		workspaceWidth: 460,
		explorerWidth: 220,
		...readJSON(PREFS_KEY, {}),
	}
	if (typeof prefs.customInstructions !== "string") prefs.customInstructions = ""

	const state = reactive({
		sessions: [],
		sessionId: null,
		session: null, // GET /sessions/{sid} payload
		conversation: initialConversation(),
		queued: [], // steered messages not yet durable
		models: [],
		modelErrors: [],
		tools: [], // what the daemon lets a session enable: { name, description, extension }
		skills: [],
		loading: false,
		toast: null,
		draft: null, // { text, attachments } handed to the composer after rewind
		codeRefs: [], // { path, rel, start, end } selections queued for the next message
		// right panel; tabs are typed ({ kind: "editor" } today, browser/terminal
		// later) — editor tabs: { kind, path, name, content, error, loading, dirty },
		// content being the last server-confirmed text (the editor owns unsaved edits)
		workspace: { open: false, maximized: false, tabs: [], active: null, view: null },
		settingsOpen: false,
		prefs,
		// agent presets: { id, name, tools, extensionTools, promptMode, prompt }
		presets: [].concat(readJSON(PRESETS_KEY, [])).filter(
			(p) => p && typeof p.id === "string" && Array.isArray(p.tools),
		),
		titles: readJSON(TITLES_KEY, {}),
		sessionPresets: readJSON(SESSION_PRESETS_KEY, {}), // session id -> the preset it was created with
	})

	let stream = null
	let streamTask = null
	let creating = null // in-flight lazy session creation; a double-send shares it
	let loadingSkills = null // { cwd, promise }
	let previewedSkillsFor = null

	function savePrefs() {
		localStorage.setItem(PREFS_KEY, JSON.stringify(state.prefs))
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
		localStorage.setItem(TITLES_KEY, JSON.stringify(state.titles))
	}

	function sessionTitle(info) {
		return (
			info.title ??
			state.titles[info.session_id] ??
			`${(info.cwd ?? "").split("/").filter(Boolean).pop() ?? "session"} · ${info.session_id.slice(0, 8)}`
		)
	}

	async function refreshSessions() {
		const data = await guard(() => client.sessions())
		if (!data) return
		state.sessions = data.sessions
		// drop stored panel state for sessions deleted outside this UI
		const known = new Set(data.sessions.map((info) => info.session_id))
		const stale = Object.keys(workspaceBySession).filter((sid) => !known.has(sid))
		if (stale.length) {
			for (const sid of stale) delete workspaceBySession[sid]
			localStorage.setItem(WORKSPACE_KEY, JSON.stringify(workspaceBySession))
		}
	}

	async function refreshModels() {
		const data = await guard(() => client.models())
		if (data) {
			state.models = data.models
			state.modelErrors = data.errors ?? []
		}
	}

	// silent: an older daemon has no /tools route, and the list is optional
	async function refreshTools() {
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
	let workspaceBySession = readJSON(WORKSPACE_KEY, {})

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
				tabs: ws.tabs.map((t) => ({ path: t.path, diff: !!t.diff })),
			}
		} else {
			delete workspaceBySession[sid]
		}
		localStorage.setItem(WORKSPACE_KEY, JSON.stringify(workspaceBySession))
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
		state.workspace = {
			open: saved.open ?? true,
			maximized: (saved.open ?? true) && !!saved.maximized,
			view: ["files", "diff"].includes(saved.view) ? saved.view : null,
			tabs: stored.map(({ path, diff }) => ({
				kind: "editor",
				path,
				name: path.split(/[\\/]/).filter(Boolean).pop() ?? path,
				content: null,
				original: null,
				error: null,
				loading: false,
				dirty: false,
				diff: !!diff,
			})),
			active: saved.active == null ? null : paths.includes(saved.active) ? saved.active : (paths[0] ?? null),
		}
	}

	async function openSession(sid) {
		closeStream()
		// a same-session reload (rewind) keeps the open file tabs as they are
		const switching = state.sessionId !== sid
		if (switching) resetWorkspace()
		state.sessionId = sid
		if (switching) restoreWorkspace(sid)
		// seed cwd/title from the session list so the header doesn't flash empty
		// while the full session loads
		const listed = state.sessions.find((s) => s.session_id === sid)
		state.session = listed ? { title: sessionTitle(listed), config: { cwd: listed.cwd } } : null
		state.queued = []
		state.skills = []
		state.conversation = initialConversation()
		state.loading = true
		const [info, catalog] = await Promise.all([
			guard(() => client.session(sid)),
			typeof client.skills === "function"
				? guard(() => client.skills(sid))
				: Promise.resolve({ skills: [] }),
		])
		if (state.sessionId !== sid) return
		if (!info) {
			state.session = null // drop the list seed — the load failed
			state.loading = false
			return
		}
		// Seed from the active branch, not a raw-log replay: the log also holds
		// rewind markers and abandoned rows, which must never enter the
		// transcript (a replayed rewind would trigger an endless reload loop).
		const seed = await guard(() => client.entries(sid))
		if (state.sessionId !== sid) return
		if (!seed) {
			state.session = null // drop the list seed — the load failed
			state.loading = false
			return
		}
		if (seed.latest_seq > info.latest_seq) info.latest_seq = seed.latest_seq
		state.session = info
		// hydrate the restored active tab now that the session's cwd is known
		if (switching && state.workspace.open && state.workspace.active)
			selectFile(state.workspace.active)
		state.skills = catalog?.skills ?? []
		state.conversation.model = info.model
		state.conversation.reasoningEffort = info.reasoning_effort ?? null
		state.conversation.contextTokens = info.context_tokens ?? 0
		for (const entry of seed.entries) applyEvent(state.conversation, entry)
		// A trailing model_changed has no usage yet, so fall back to the selected
		// model's static limit from the session detail response.
		state.conversation.contextWindow ??= info.context_window ?? null
		state.prefs.lastSession = sid // restored on the next page load
		savePrefs()
		state.loading = false
		startStream(sid, seed.latest_seq)
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
				if (state.sessionId === sid) state.loading = false
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
		if (event.type === "run_error" && event.seq > (state.session?.latest_seq ?? 0)) {
			state.conversation.liveErrorSeqs.push(event.seq)
		}
		applyEvent(state.conversation, event)
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
			const queued = state.queued.findIndex(
				(item) => item.text === text && sameArray(item.attachmentIds, attachmentIds),
			)
			if (queued !== -1) state.queued.splice(queued, 1)
			rememberTitle(sid)
		}
		// refresh the picker only for live run boundaries, not replayed history
		if (
			(event.type === "run_started" || event.type === "run_ended") &&
			event.seq > (state.session?.latest_seq ?? 0)
		) {
			refreshSessions()
		}
	}

	// Reset to the blank "new chat" state, carrying the active project's cwd
	// unless the caller supplies one. No server call — send() creates it lazily.
	function startNewChat({ cwd = null } = {}) {
		const listedSession = state.sessions.find((session) => session.session_id === state.sessionId)
		const nextCwd = cwd ?? state.session?.config?.cwd ?? listedSession?.cwd
		closeStream()
		resetWorkspace()
		state.sessionId = null
		state.session = null
		state.queued = []
		state.skills = []
		state.conversation = initialConversation()
		previewedSkillsFor = null
		state.prefs.lastSession = null
		if (nextCwd) state.prefs.cwd = nextCwd
		savePrefs()
	}

	async function newSession({ cwd = null, model = null } = {}) {
		const preset = activePreset()
		const config = {
			auto_approve: state.prefs.mode === "auto",
		}
		if (preset?.tools) config.tools = preset.tools
		if (preset?.extensionTools) config.extension_tools = preset.extensionTools
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
		if (preset) {
			state.sessionPresets[data.session_id] = preset.id
			localStorage.setItem(SESSION_PRESETS_KEY, JSON.stringify(state.sessionPresets))
		}
		const effort = state.prefs.lastEffort
		if (effort) {
			await guard(() =>
				client.setModel(data.session_id, {
					model: useModel ?? data.config.model,
					reasoning_effort: effort === "default" ? null : effort,
				}),
			)
		}
		await refreshSessions()
		await openSession(data.session_id)
		return data.session_id
	}

	async function loadSkills() {
		if (state.sessionId || typeof client.previewSkills !== "function") return
		const cwd = state.prefs.cwd ?? ""
		if (previewedSkillsFor === cwd) return
		const pending =
			loadingSkills?.cwd === cwd
				? loadingSkills.promise
				: guard(() => client.previewSkills(cwd ? { cwd } : {}))
		loadingSkills = { cwd, promise: pending }
		try {
			const catalog = await pending
			if (!state.sessionId && (state.prefs.cwd ?? "") === cwd && catalog) {
				state.skills = catalog.skills ?? []
				previewedSkillsFor = cwd
			}
		} finally {
			if (loadingSkills?.promise === pending) loadingSkills = null
			if (!state.sessionId && (state.prefs.cwd ?? "") !== cwd) void loadSkills()
		}
	}

	async function send(text, attachments = []) {
		const message = text.trim()
		if (!message && !attachments.length) return false
		if (!state.sessionId) {
			if (!state.prefs.cwd) {
				notify("Choose a project folder before sending a message.", "error")
				return false
			}
			creating ??= newSession()
			try {
				if (!(await creating)) return false
			} finally {
				creating = null
			}
		}
		const sid = state.sessionId
		const attachmentIds = attachments.filter((item) => item.id).map((item) => item.id)
		const createdIds = []
		let admitted = false
		try {
			const uploads = attachments.filter((item) => item.file).map((item) => item.file)
			if (uploads.length) {
				const uploaded = await guard(() => client.uploadAttachments(sid, uploads))
				if (!uploaded) return false
				const ids = uploaded.attachments.map((item) => item.id)
				attachmentIds.push(...ids)
				createdIds.push(...ids)
			}
			const result = await guard(() => client.run(sid, message, attachmentIds))
			if (!result) return false
			admitted = true
			if (result.status === "steered" && state.sessionId === sid) {
				state.queued.push({
					text: normalizeSkillCommand(message) ?? message,
					attachmentIds,
					label: message || `${attachments.length} attachment(s)`,
				})
			}
			return true
		} finally {
			if (!admitted && createdIds.length) {
				// A claimed attachment is retained if the run reached the daemon but its
				// response was lost; only genuinely unclaimed staging data is removed.
				await client.cleanupAttachments(sid, createdIds).catch(() => {})
			}
		}
	}

	// Approval answers: "Approve" | "Deny" | free text. Resume fires once every
	// undecided call in the batch has an answer (the server validates exactness).
	// A deny stops the run, so it settles the batch: undecided calls deny with it
	// (explicit answers stand, matching the server's approve-then-halt order).
	async function answerApproval(callId, answer) {
		const pending = state.conversation.pendingApproval
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
		state.queued = []
		await guard(() => client.abort(state.sessionId))
	}

	async function cancelPending() {
		if (!state.sessionId) return
		await guard(() => client.cancelPending(state.sessionId))
	}

	async function compact() {
		if (!state.sessionId) return
		await guard(() => client.compact(state.sessionId))
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
		// the confirm dialog may outlive a session switch — this entry's seqs
		// only mean anything in the conversation it came from
		if (!state.conversation.entries.includes(entry)) return null
		// branch from the entry before the message's run_started; the message's
		// parent chain makes parent_seq the correct anchor
		const target = (entry.parent_seq ?? 1) - 1
		const ok = await guard(() => client.rewind(state.sessionId, Math.max(target, 0)))
		if (ok === null) return null
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
		const last = [...state.conversation.entries].reverse().find((e) => e.type === "user_message")
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
		if (state.codeRefs.some((r) => r.path === path && r.start === start && r.end === end)) return
		state.codeRefs.push({ path, rel, start, end })
	}

	function removeCodeRef(index) {
		state.codeRefs.splice(index, 1)
	}

	function clearCodeRefs() {
		state.codeRefs = []
	}

	async function selectModel(model) {
		state.prefs.lastModel = model
		savePrefs()
		if (!state.sessionId) return
		const data = await guard(() =>
			client.setModel(state.sessionId, {
				model,
				reasoning_effort:
					state.prefs.lastEffort && state.prefs.lastEffort !== "default" ? state.prefs.lastEffort : null,
			}),
		)
		if (!data) return
		state.conversation.model = data.model
		state.conversation.contextWindow = data.context_window ?? null
		if (state.session) {
			state.session.model = data.model
			state.session.context_window = data.context_window ?? null
			state.session.supports_images = data.supports_images
		}
	}

	async function selectEffort(effort) {
		state.prefs.lastEffort = effort
		savePrefs()
		if (!state.sessionId) return
		const model = state.conversation.model ?? state.session?.model
		if (!model) return
		await guard(() =>
			client.setModel(state.sessionId, {
				model,
				reasoning_effort: effort === "default" ? null : effort,
			}),
		)
		state.conversation.reasoningEffort = effort === "default" ? null : effort
	}

	// Approval mode: remembered for new chats, and applied to the current session
	// immediately — mid-run flips take effect at the next tool gate.
	async function setMode(mode) {
		state.prefs.mode = mode
		savePrefs()
		if (!state.sessionId) return
		const data = await guard(() =>
			client.patchConfig(state.sessionId, { auto_approve: mode === "auto" }),
		)
		if (!data) return // the server never switched; don't act on the new mode
		if (state.session) state.session.config = data.config
		// a batch already waiting at the gate is covered by the new mode: approve
		// whatever the user hasn't decided yet (their explicit answers stand)
		const pending = state.conversation.pendingApproval
		if (mode === "auto" && pending) {
			for (const call of pending.calls) {
				if (!(call.id in pending.answers)) await answerApproval(call.id, "Approve")
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
			previewedSkillsFor = null
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

	// the "+ → Files" view: panel open with no active tab, explorer as the focus
	function showFilesView() {
		state.workspace.open = true
		state.workspace.view = "files"
		state.workspace.active = null
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
		if (tab.content == null && !tab.loading && !tab.error)
			void (tab.diff ? openDiffFile(path) : openFile(path))
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
		tab.content = content
		tab.dirty = false
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
		if (ws.active === path) ws.active = ws.tabs[Math.min(index, ws.tabs.length - 1)]?.path ?? null
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
		state.prefs.sidebarOpen = open
		savePrefs()
	}

	function setSidebarWidth(width) {
		state.prefs.sidebarWidth = width
		savePrefs()
	}

	function setCustomInstructions(text) {
		state.prefs.customInstructions = text
		savePrefs()
	}

	function setSettingsOpen(open) {
		state.settingsOpen = open
	}

	function savePresets() {
		localStorage.setItem(PRESETS_KEY, JSON.stringify(state.presets))
	}

	function activePreset() {
		return state.presets.find((p) => p.id === state.prefs.activePreset) ?? null
	}

	// create (no id) or update; returns the id
	function savePreset(preset) {
		const id = preset.id ?? crypto.randomUUID()
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
		for (const [sid, presetId] of Object.entries(state.sessionPresets)) {
			if (presetId === id) delete state.sessionPresets[sid]
		}
		localStorage.setItem(SESSION_PRESETS_KEY, JSON.stringify(state.sessionPresets))
	}

	function setActivePreset(id) {
		state.prefs.activePreset = id
		savePrefs()
	}

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
			localStorage.setItem(TITLES_KEY, JSON.stringify(state.titles))
		}
		if (workspaceBySession[sid]) {
			delete workspaceBySession[sid]
			localStorage.setItem(WORKSPACE_KEY, JSON.stringify(workspaceBySession))
		}
		if (state.sessionPresets[sid]) {
			delete state.sessionPresets[sid]
			localStorage.setItem(SESSION_PRESETS_KEY, JSON.stringify(state.sessionPresets))
		}
		if (state.sessionId === sid) startNewChat()
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

	function detach() {
		closeStream()
	}

	return {
		state,
		client,
		refreshSessions,
		refreshModels,
		refreshTools,
		openSession,
		startNewChat,
		newSession,
		loadSkills,
		send,
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
		selectModel,
		selectEffort,
		setMode,
		setCwd,
		openFile,
		openDiffFile,
		explorerCwd,
		listFiles,
		searchFiles,
		gitChanges,
		selectFile,
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
		setCustomInstructions,
		setSettingsOpen,
		activePreset,
		savePreset,
		deletePreset,
		setActivePreset,
		renameSession,
		deleteSession,
		pickFolder,
		sessionTitle,
		notify,
		detach,
	}
}
