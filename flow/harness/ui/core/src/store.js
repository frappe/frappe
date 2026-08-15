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
	const state = reactive({
		sessions: [],
		sessionId: null,
		session: null, // GET /sessions/{sid} payload
		conversation: initialConversation(),
		queued: [], // steered messages not yet durable
		models: [],
		modelErrors: [],
		skills: [],
		loading: false,
		toast: null,
		draft: null, // { text, attachments } handed to the composer after rewind
		prefs: {
			theme: "light",
			mode: "ask", // "ask" | "auto" — applied at session create
			lastModel: null,
			lastEffort: null,
			cwd: null,
			sidebarOpen: true,
			...readJSON(PREFS_KEY, {}),
		},
		titles: readJSON(TITLES_KEY, {}),
	})

	let stream = null
	let streamTask = null
	let creating = null // in-flight lazy session creation; a double-send shares it
	let loadingSkills = null // { cwd, promise }
	let previewedSkillsFor = null

	function savePrefs() {
		localStorage.setItem(PREFS_KEY, JSON.stringify(state.prefs))
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
		if (data) state.sessions = data.sessions
	}

	async function refreshModels() {
		const data = await guard(() => client.models())
		if (data) {
			state.models = data.models
			state.modelErrors = data.errors ?? []
		}
	}

	function closeStream() {
		stream?.close()
		stream = null
		streamTask = null
	}

	async function openSession(sid) {
		closeStream()
		state.sessionId = sid
		state.session = null
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
			state.loading = false
			return
		}
		// Seed from the active branch, not a raw-log replay: the log also holds
		// rewind markers and abandoned rows, which must never enter the
		// transcript (a replayed rewind would trigger an endless reload loop).
		const seed = await guard(() => client.entries(sid))
		if (state.sessionId !== sid) return
		if (!seed) {
			state.loading = false
			return
		}
		if (seed.latest_seq > info.latest_seq) info.latest_seq = seed.latest_seq
		state.session = info
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
		const config = {
			auto_approve: state.prefs.mode === "auto",
		}
		const useCwd = cwd ?? state.prefs.cwd
		if (useCwd) config.cwd = useCwd
		const useModel = model ?? state.prefs.lastModel
		if (useModel) config.model = useModel
		const data = await guard(() => client.createSession(config), { rethrow: false })
		if (!data) return null
		if (state.prefs.lastEffort) {
			await guard(() =>
				client.setModel(data.session_id, {
					model: useModel ?? data.config.model,
					reasoning_effort: state.prefs.lastEffort === "default" ? null : state.prefs.lastEffort,
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
	async function answerApproval(callId, answer) {
		const pending = state.conversation.pendingApproval
		if (!pending) return
		pending.answers[callId] = answer
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
		state.prefs.cwd = path
		if (!state.sessionId) {
			state.skills = []
			previewedSkillsFor = null
		}
		savePrefs()
	}

	function setSidebarOpen(open) {
		state.prefs.sidebarOpen = open
		savePrefs()
	}

	function setTheme(theme) {
		state.prefs.theme = theme
		savePrefs()
		document.documentElement.setAttribute("data-theme", theme)
	}

	async function deleteSession(sid) {
		const ok = await guard(() => client.deleteSession(sid))
		if (ok === null) return // running (409) or gone — the toast already said so
		state.sessions = state.sessions.filter((s) => s.session_id !== sid)
		if (state.titles[sid]) {
			delete state.titles[sid]
			localStorage.setItem(TITLES_KEY, JSON.stringify(state.titles))
		}
		if (state.sessionId === sid) startNewChat()
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
		openSession,
		startNewChat,
		newSession,
		loadSkills,
		send,
		answerApproval,
		abort,
		cancelPending,
		compact,
		rewindToMessage,
		rewindLastUserMessage,
		setDraft,
		selectModel,
		selectEffort,
		setMode,
		setCwd,
		setSidebarOpen,
		setTheme,
		deleteSession,
		pickFolder,
		sessionTitle,
		notify,
		detach,
	}
}
