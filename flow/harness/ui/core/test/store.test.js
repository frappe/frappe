import assert from "node:assert/strict"
import test from "node:test"
import { ref } from "vue"

import { FlowAPIError } from "../src/client.js"
import { layout } from "../src/layout.js"
import { createFlowStore, MAX_ATTACHMENTS } from "../src/store.js"
import { applyEvent } from "../src/transcript.js"

globalThis.localStorage = {
	getItem() {
		return null
	},
	setItem() {},
}

test("the session list pages past the last row shown and searches through the host", async () => {
	const calls = []
	const rows = (from, n) =>
		Array.from({ length: n }, (_, i) => ({ session_id: `s${from + i}`, modified: `t${from + i}` }))
	const client = {
		async sessions({ query, before }) {
			calls.push([query, before])
			if (query) return { sessions: rows(9, 1), more: false }
			return before ? { sessions: rows(2, 1), more: false } : { sessions: rows(0, 2), more: true }
		},
	}
	const flow = createFlowStore(client)
	await flow.refreshSessions()
	assert.equal(flow.state.sessionsMore, true)

	// a full page: the search goes to the host, and clearing it reloads the list
	await flow.searchSessions("read")
	assert.deepEqual(flow.state.sessions.map((s) => s.session_id), ["s9"])
	await flow.searchSessions("")
	assert.deepEqual(flow.state.sessions.map((s) => s.session_id), ["s0", "s1"])

	// a search cleared before its answer lands leaves the full list
	await Promise.all([flow.searchSessions("alp"), flow.searchSessions("")])
	assert.deepEqual(flow.state.sessions.map((s) => s.session_id), ["s0", "s1"])
	assert.equal(flow.state.sessionQuery, "")

	// the next page appends once, however often the sentinel asks
	await Promise.all([flow.loadMoreSessions(), flow.loadMoreSessions()])
	assert.deepEqual(flow.state.sessions.map((s) => s.session_id), ["s0", "s1", "s2"])
	assert.equal(flow.state.sessionsMore, false)
	assert.equal(flow.loadMoreSessions(), undefined)

	// every session loaded: typing filters locally, no request
	await flow.searchSessions("read")
	assert.deepEqual(calls, [
		["", undefined],
		["read", undefined],
		["", undefined],
		["alp", undefined],
		["", undefined],
		["", "t1"],
	])
})

test("send stages uploads and mentions side by side, and sends a prepared file by id", async () => {
	const calls = []
	let uploadFinished = false
	let mentionRanBeforeUploadFinished = false
	const client = {
		async uploadAttachments(sid, files) {
			calls.push(["upload", sid, files.map((file) => file.name)])
			await new Promise((resolve) => setTimeout(resolve, 10))
			uploadFinished = true
			return { attachments: [{ id: "att-upload" }] }
		},
		async attachFiles(sid, paths) {
			calls.push(["attach", sid, paths])
			// staged one after the other, this would only run once the upload finished
			if (!uploadFinished) mentionRanBeforeUploadFinished = true
			return { attachments: paths.map((path, i) => ({ id: `att-${i}`, name: path })) }
		},
		async run(sid, message, ids) {
			calls.push(["run", sid, message, ids])
			return { status: "ok" }
		},
	}
	const flow = createFlowStore(client)
	flow.state.sessionId = "session-1"

	const sent = await flow.send("check these", [
		{ id: "F1", file: { name: "notes.pdf" } }, // prepared: not uploaded again
		{ key: "local:0", name: "screen.png", kind: "image", file: { name: "screen.png" } },
		{ key: "mention:0", name: "foo.py", kind: "file", mentionPath: "src/foo.py" },
	])

	assert.equal(sent, true)
	assert.equal(mentionRanBeforeUploadFinished, true)
	assert.deepEqual(calls, [
		["upload", "session-1", ["screen.png"]],
		["attach", "session-1", ["src/foo.py"]],
		["run", "session-1", "check these", ["F1", "att-upload", "att-0"]],
	])
})

test("skill previews load once per folder and never land in another folder's list", async () => {
	const requests = []
	const client = {
		previewSkills(config) {
			return new Promise((resolve) => requests.push({ cwd: config.cwd, resolve }))
		},
	}
	const flow = createFlowStore(client)
	flow.setCwd("/first")
	const first = Promise.all([flow.loadSkills(), flow.loadSkills()])
	flow.setCwd("/second")
	const second = flow.loadSkills()
	assert.deepEqual(
		requests.map((request) => request.cwd),
		["/first", "/second"],
	)

	requests[0].resolve({ skills: [{ name: "first" }] })
	await first
	assert.deepEqual(flow.state.skills, [])

	requests[1].resolve({ skills: [{ name: "second", description: "Review changes" }] })
	await second
	assert.deepEqual(flow.state.skills, [{ name: "second", description: "Review changes" }])
	assert.equal(flow.state.sessionId, null)
})

test("an open session refetches its skills only when forced, and the newest refetch wins", async () => {
	const requests = []
	const client = {
		async session() {
			return { session_id: "s1", model: "m", latest_seq: 1 }
		},
		async entries() {
			return { entries: [], latest_seq: 1 }
		},
		skills(sid) {
			assert.equal(sid, "s1")
			return new Promise((resolve) => requests.push(resolve))
		},
		stream() {
			return { close() {}, async *[Symbol.asyncIterator]() {} }
		},
	}
	const flow = createFlowStore(client)
	const names = () => flow.state.skills.map((skill) => skill.name)
	const opened = flow.openSession("s1")
	requests[0]({ skills: [{ name: "review" }] })
	await opened
	await flow.loadSkills()
	assert.equal(requests.length, 1)
	assert.deepEqual(names(), ["review"])

	// a skill written after the session started is invocable, so a forced refetch lists it
	const stale = flow.loadSkills({ force: true })
	const fresh = flow.loadSkills({ force: true })
	requests[2]({ skills: [{ name: "review" }, { name: "testing" }] })
	await fresh
	requests[1]({ skills: [{ name: "review" }] })
	await stale
	assert.deepEqual(names(), ["review", "testing"])
	flow.detach()
})

test("a chat opens once, stays loading until its own load lands, and gives way to a blank chat", async () => {
	const answers = []
	const streams = []
	const client = {
		session: (sid) => new Promise((resolve, reject) => answers.push({ sid, resolve, reject })),
		async entries() {
			return {
				entries: [
					{ type: "user_message", seq: 1, content: "hi" },
					{ type: "assistant_message", seq: 2, content: [{ type: "text", text: "hello" }] },
				],
				latest_seq: 2,
			}
		},
		// a live stream stays open until it is closed
		stream(sid) {
			streams.push(sid)
			let finish
			const closed = new Promise((resolve) => (finish = resolve))
			return {
				close: () => finish(),
				async *[Symbol.asyncIterator]() {
					await closed
				},
			}
		},
	}
	const flow = createFlowStore(client)
	flow.state.sessions = [{ session_id: "A", title: "Fix the bug", cwd: "/projects/active" }]
	const answer = () => {
		const { sid, resolve } = answers.shift()
		resolve({ session_id: sid, model: "m", latest_seq: 2 })
	}

	// a double-click shows the history once, on one stream
	const opens = [flow.openSession("A"), flow.openSession("A")]
	answer()
	answer()
	await Promise.all(opens)
	assert.deepEqual(flow.state.conversation.entries.map((entry) => entry.seq), [1, 2])
	assert.deepEqual(streams, ["A"])

	// reopening the open chat keeps it loading until the reload lands
	const reopened = flow.openSession("A")
	await settle() // the old stream winds down
	assert.equal(flow.state.loading, true)
	answer()
	await reopened
	assert.equal(flow.state.loading, false)

	// a new chat carries the open chat's folder, or the one picked
	flow.startNewChat()
	assert.equal(flow.state.prefs.cwd, "/projects/active")
	flow.startNewChat({ cwd: "/projects/selected" })
	assert.equal(flow.state.prefs.cwd, "/projects/selected")

	// a new chat started while a chat loads is not left loading
	const opened = flow.openSession("A")
	assert.equal(flow.state.loading, true)
	flow.startNewChat()
	assert.equal(flow.state.loading, false)
	answer()
	await opened
	assert.equal(flow.state.loading, false)
	assert.equal(flow.state.sessionId, null)

	// a chat that fails to load leaves a blank chat, not one that can't send
	const failed = flow.openSession("gone")
	answers.shift().reject(new FlowAPIError(404, "session not found"))
	await failed
	assert.equal(flow.state.sessionId, null)
	assert.equal(flow.state.loading, false)
	assert.equal(flow.state.toast.message, "session not found")
	flow.detach()
})

test("only the latest model refresh ends the loading and fills the list", async () => {
	const answers = []
	const flow = createFlowStore({ models: () => new Promise((resolve) => answers.push(resolve)) })
	const first = flow.refreshModels()
	const second = flow.refreshModels()
	answers[0]({ models: [{ name: "old/model", provider: "old" }] })
	await first
	assert.equal(flow.state.modelsLoading, true)
	assert.deepEqual(flow.state.models, [])
	answers[1]({ models: [{ name: "new/model", provider: "new" }] })
	await second
	assert.equal(flow.state.modelsLoading, false)
	assert.deepEqual(
		flow.state.models.map((model) => model.name),
		["new/model"],
	)
})

test("a chat being opened shows its model once known, or its list row's when the host vouches for it", async () => {
	let respond
	const changes = []
	const client = {
		session: () => new Promise((resolve) => (respond = resolve)),
		async entries() {
			return { entries: [], latest_seq: 1 }
		},
		async setModel(sid, body) {
			changes.push(body)
			return body
		},
		stream() {
			return { close() {}, async *[Symbol.asyncIterator]() {} }
		},
	}
	const flow = createFlowStore(client)
	// a cold chat's list row can lag a later model change
	flow.state.sessions = [{ session_id: "s1", model: "openai/created-with" }]
	const opened = flow.openSession("s1")
	assert.equal(flow.state.conversation.model, null)
	// an effort picked meanwhile changes no model
	await flow.selectEffort("high")
	assert.deepEqual(changes, [])
	respond({ session_id: "s1", model: "openai/current", latest_seq: 1 })
	await opened
	assert.equal(flow.state.conversation.model, "openai/current")

	// a chat just created already knows its model
	const created = flow.openSession("s2", { config: { model: "openai/new" } })
	assert.equal(flow.state.conversation.model, "openai/new")
	respond({ session_id: "s2", model: "openai/new", latest_seq: 1 })
	await created
	flow.detach()

	// a host whose list carries the current model shows it while a chat opens
	const listed = createFlowStore(client, { listedModel: true })
	listed.state.sessions = [{ session_id: "a", model: "m/a" }]
	const opening = listed.openSession("a")
	assert.equal(listed.state.conversation.model, "m/a")
	respond({ session_id: "a", model: "m/a", latest_seq: 1 })
	await opening
	listed.detach()
})

test("a change that answers after a chat switch stays with the chat it was made in", async () => {
	const models = []
	let modeAnswer
	let rewindAnswer
	const resumes = []
	const client = hostClient([])
	client.session = async (sid) => ({ session_id: sid, model: `m/${sid}`, latest_seq: 2, config: { cwd: `/${sid}` } })
	client.entries = async () => ({
		entries: [{ type: "user_message", seq: 2, parent_seq: 1, content: "fix it" }],
		latest_seq: 2,
	})
	client.setModel = () => new Promise((resolve) => models.push(resolve))
	client.patchConfig = () => new Promise((resolve) => (modeAnswer = resolve))
	client.rewind = () => new Promise((resolve) => (rewindAnswer = resolve))
	client.resume = async (sid, seq, answers) => {
		resumes.push([sid, seq, answers])
		return { status: "resumed" }
	}
	const flow = createFlowStore(client)
	flow.state.sessions = [
		{ session_id: "A", model: "m/A" },
		{ session_id: "B", model: "m/B" },
	]
	await flow.openSession("A")

	const changes = [
		flow.selectModel("m/new"),
		flow.selectEffort("high"),
		flow.setMode("auto"),
		flow.rewindLastUserMessage(),
	]
	await flow.openSession("B")
	flow.state.conversation.pendingApproval = { seq: 2, calls: [{ id: "x" }], answers: {} }
	models[0]({ model: "m/new" })
	models[1]({ model: "m/A", reasoning_effort: "high" })
	modeAnswer({ config: { auto_approve: true, cwd: "/A" } })
	rewindAnswer({ status: "rewound" })
	const rewound = (await Promise.all(changes))[3]

	// the model change keeps its own chat's row current, for when it reopens
	assert.deepEqual(
		flow.state.sessions.map((s) => s.model),
		["m/new", "m/B"],
	)
	assert.equal(flow.state.conversation.model, "m/B")
	assert.equal(flow.state.conversation.reasoningEffort, null)
	assert.deepEqual(resumes, [])
	assert.equal(flow.state.session.config.cwd, "/B")
	assert.equal(rewound, null)
	assert.equal(flow.state.draft, null)
	flow.detach()
})

test("a send that fails cleans up the files it staged", async () => {
	const mention = { key: "mention:0", name: "foo.py", kind: "file", mentionPath: "src/foo.py" }
	const upload = { key: "local:0", name: "screen.png", kind: "image", file: {} }
	// the run fails after the mention resolved, or the upload beside it fails
	for (const [failing, attachments] of [
		["run", [mention]],
		["upload", [upload, mention]],
	]) {
		const cleaned = []
		const client = {
			async uploadAttachments() {
				throw new Error("upload failed")
			},
			async attachFiles() {
				return { attachments: [{ id: "att-mention" }] }
			},
			async run() {
				throw new Error("boom")
			},
			async cleanupAttachments(sid, ids) {
				cleaned.push({ sid, ids })
			},
		}
		const flow = createFlowStore(client)
		flow.state.sessionId = "session-1"

		assert.equal(await flow.send("check this file", attachments), false, failing)
		assert.deepEqual(cleaned, [{ sid: "session-1", ids: ["att-mention"] }], failing)
	}
})

test("uploads and mentions share one cap, the host's or the default, checked before staging", async () => {
	// each staging endpoint caps on its own, so 6 + 6 passes both; only their sum rides the run
	const mixed = [
		...Array.from({ length: 6 }, (_, i) => ({ key: `local:${i}`, kind: "image", file: {} })),
		...Array.from({ length: 6 }, (_, i) => ({ key: `mention:${i}`, kind: "file", mentionPath: `f${i}.py` })),
	]
	assert.equal(mixed.length, MAX_ATTACHMENTS + 2)
	for (const [options, attachments, toast] of [
		[{}, mixed, /at most 10 attachments/],
		[{ maxAttachments: 2 }, mixed.slice(0, 3), /at most 2 attachments/],
	]) {
		const calls = []
		const client = {
			async uploadAttachments() {
				calls.push("upload")
				return { attachments: [] }
			},
			async attachFiles() {
				calls.push("attach")
				return { attachments: [] }
			},
			async run() {
				calls.push("run")
				return { status: "ok" }
			},
		}
		const flow = createFlowStore(client, options)
		flow.state.sessionId = "session-1"

		assert.equal(await flow.send("too many", attachments), false, String(toast))
		assert.deepEqual(calls, [], String(toast)) // nothing staged, so nothing to clean up
		assert.match(flow.state.toast.message, toast)
	}
})

function approvalStore(resumes) {
	const client = {
		async resume(sessionId, seq, answers) {
			resumes.push({ seq, answers })
			return {}
		},
	}
	const flow = createFlowStore(client)
	flow.state.sessionId = "session-1"
	flow.state.conversation.pendingApproval = {
		seq: 7,
		calls: [{ id: "c1" }, { id: "c2" }],
		answers: {},
	}
	return flow
}

test("an approval batch resumes once every call is answered; a deny settles the undecided rest", async () => {
	const resumes = []
	const flow = approvalStore(resumes)
	await flow.answerApproval("c1", "Approve")
	assert.equal(resumes.length, 0) // still waiting on c2
	await flow.answerApproval("c2", "Deny")
	assert.deepEqual(resumes, [{ seq: 7, answers: { c1: "Approve", c2: "Deny" } }]) // the approve stands

	const denied = []
	await approvalStore(denied).answerApproval("c1", "Deny")
	assert.deepEqual(denied, [{ seq: 7, answers: { c1: "Deny", c2: "Deny" } }])
})

test("a model the chat takes updates its header and the default; a refused one doesn't", async (t) => {
	const stored = []
	const storage = globalThis.localStorage
	globalThis.localStorage = { getItem: () => null, setItem: (key, value) => stored.push(value) }
	t.after(() => (globalThis.localStorage = storage))
	let refuse = true
	const client = {
		async setModel(sessionId, selection) {
			if (refuse) throw new FlowAPIError(409, "a run is already active")
			assert.equal(sessionId, "session-1")
			assert.equal(selection.model, "deepseek/deepseek-chat")
			return {
				model: selection.model,
				context_window: 1_000_000,
				supports_images: false,
			}
		},
	}
	const flow = createFlowStore(client)
	flow.state.sessionId = "session-1"
	flow.state.session = {
		model: "codex/gpt-5.6-sol",
		context_window: 272_000,
		supports_images: true,
	}
	flow.state.conversation.model = "codex/gpt-5.6-sol"
	flow.state.conversation.contextWindow = 272_000

	// a running chat refuses a model or thinking level: neither becomes the default
	await flow.selectModel("other/model")
	await flow.selectEffort("high")
	assert.equal(flow.state.prefs.lastModel, null)
	assert.equal(flow.state.prefs.lastEffort, null)

	refuse = false
	await flow.selectModel("deepseek/deepseek-chat")
	assert.equal(flow.state.conversation.model, "deepseek/deepseek-chat")
	assert.equal(flow.state.conversation.contextWindow, 1_000_000)
	assert.equal(flow.state.session.context_window, 1_000_000)

	// a model the host renamed stays the one a new chat starts with
	flow.renamedModel("other/model", "x/y")
	assert.equal(flow.state.prefs.lastModel, "deepseek/deepseek-chat")
	flow.renamedModel("deepseek/deepseek-chat", "deepseek/v4")
	assert.equal(flow.state.prefs.lastModel, "deepseek/v4")
	assert.equal(JSON.parse(stored.at(-1)).lastModel, "deepseek/v4")
	flow.detach()
})

test("a reopened chat restores its model's limit and the reply still streaming", async () => {
	let releaseSuffix
	let prefixDelivered
	let suffixDelivered
	const suffixGate = new Promise((resolve) => (releaseSuffix = resolve))
	const sawPrefix = new Promise((resolve) => (prefixDelivered = resolve))
	const sawSuffix = new Promise((resolve) => (suffixDelivered = resolve))
	const client = {
		async session() {
			return {
				session_id: "s1",
				model: "deepseek/deepseek-chat",
				context_window: 1_000_000,
				running: true,
				latest_seq: 3,
			}
		},
		async entries() {
			return {
				entries: [
					// no usage after this model change: the selected model's limit stands in
					{ type: "model_changed", seq: 1, model: "deepseek/deepseek-chat" },
					{ type: "run_started", seq: 2, run_id: "r1" },
					{ type: "user_message", seq: 3, content: "write a story" },
				],
				latest_seq: 3,
			}
		},
		stream(sid, since) {
			assert.equal(sid, "s1")
			assert.equal(since, 3)
			return {
				close() {},
				async *[Symbol.asyncIterator]() {
					yield { type: "preview_replay_started" }
					yield { type: "text_delta", text: "prefix" }
					prefixDelivered()
					await suffixGate
					yield { type: "text_delta", text: " suffix" }
					suffixDelivered()
				},
			}
		},
	}
	const flow = createFlowStore(client)

	await flow.openSession("s1")
	assert.equal(flow.state.conversation.model, "deepseek/deepseek-chat")
	assert.equal(flow.state.conversation.contextWindow, 1_000_000)
	await sawPrefix
	assert.deepEqual(flow.state.conversation.partial, [{ type: "text", text: "prefix" }])
	assert.deepEqual(flow.state.conversation.entries.map((entry) => entry.type), ["user_message"])

	releaseSuffix()
	await sawSuffix
	assert.deepEqual(flow.state.conversation.partial, [{ type: "text", text: "prefix suffix" }])
	flow.detach()
})

test("workspace tabs persist per session, restore after a refresh (a narrow frame's panel closed) and load as they come forward", async () => {
	const backing = new Map()
	const previousStorage = globalThis.localStorage
	globalThis.localStorage = {
		getItem: (key) => backing.get(key) ?? null,
		setItem: (key, value) => backing.set(key, value),
	}
	try {
		const client = {
			session: async () => ({ session_id: "s1", latest_seq: 0, config: { cwd: "/proj" }, model: "mock" }),
			entries: async () => ({ entries: [], latest_seq: 0 }),
			readFile: async (cwd, path) => ({ path, content: `text of ${path}` }),
			stream: () => ({ close() {}, async *[Symbol.asyncIterator]() {} }),
		}
		const flow = createFlowStore(client)
		await flow.openSession("s1")
		await flow.openFile("/proj/a.py")
		await flow.openFile("/proj/b.py")
		flow.selectFile("/proj/a.py")

		// a fresh store (page refresh) restores the same session's panel
		const restored = createFlowStore(client)
		await restored.openSession("s1")
		assert.deepEqual(
			restored.state.workspace.tabs.map((tab) => tab.path),
			["/proj/a.py", "/proj/b.py"],
		)
		assert.equal(restored.state.workspace.active, "/proj/a.py")
		assert.equal(restored.state.workspace.open, true)
		await settle()
		assert.equal(restored.state.workspace.tabs[0].content, "text of /proj/a.py") // active tab hydrated

		// a narrow frame's panel would cover the chat: it opens on the chat, the tabs kept
		layout.narrow = true
		try {
			const phone = createFlowStore(client)
			await phone.openSession("s1")
			assert.deepEqual([phone.state.workspace.open, phone.state.workspace.tabs.length], [false, 2])
		} finally {
			layout.narrow = false
		}

		// closing it loads the restored tab that comes forward
		restored.closeFile("/proj/a.py")
		await settle()
		assert.equal(restored.state.workspace.active, "/proj/b.py")
		assert.equal(restored.state.workspace.tabs[0].content, "text of /proj/b.py")

		// deleting the session drops its stored panel
		restored.state.sessions = []
		client.deleteSession = async () => ({ status: "deleted" })
		await restored.deleteSession("s1")
		const third = createFlowStore(client)
		await third.openSession("s1")
		assert.equal(third.state.workspace.tabs.length, 0)
	} finally {
		globalThis.localStorage = previousStorage
	}
})

test("files save and diff against the browsed cwd, before a session or in one", async () => {
	const calls = []
	const client = {
		async readFile(cwd, path) {
			return { path, content: "old" }
		},
		async writeFsFile(cwd, path, content) {
			calls.push(["write", cwd, path, content])
			return { path }
		},
		async gitFileDiff(cwd, path) {
			calls.push(["git", cwd, path])
			if (!path.startsWith(`${cwd}/`)) throw new FlowAPIError(400, "file is outside the repository")
			return { path, original: "old\n", modified: "new\n" }
		},
		async fileDiff(sid, path) {
			calls.push(["session", sid, path])
			return { path, original: "before\n", modified: "after\n" }
		},
		async gitChanges() {
			throw new Error("boom")
		},
		async gitBranch() {
			throw new Error("boom")
		},
	}
	const flow = createFlowStore(client)
	flow.setCwd("/project")

	// before a session: a file saves, and a diff tab loads the git diff
	await flow.openFile("/project/a.txt")
	assert.equal(await flow.saveFile("/project/a.txt", "new"), true)
	assert.equal(flow.state.workspace.tabs[0].content, "new")
	await flow.openDiffFile("/project/app.py")
	const diff = flow.state.workspace.tabs[1]
	assert.equal(diff.diff, true)
	assert.equal(diff.original, "old\n")
	assert.equal(diff.content, "new\n")
	assert.equal(flow.state.workspace.open, true)

	// the diff bar polls changes, so a failure stays silent instead of toasting, as a new chat's branch does
	assert.equal(await flow.gitChanges(), null)
	assert.equal(await flow.gitBranch(), null)
	assert.equal(flow.state.toast, null)

	// a file outside the repository falls back to the session's diff
	flow.state.sessionId = "s1"
	flow.state.session = { config: { cwd: "/project" } }
	await flow.openDiffFile("/home/elsewhere/hook.py")
	const outside = flow.state.workspace.tabs[2]
	assert.equal(outside.error, null)
	assert.equal(outside.original, "before\n")
	assert.equal(outside.content, "after\n")
	assert.deepEqual(calls, [
		["write", "/project", "/project/a.txt", "new"],
		["git", "/project", "/project/app.py"],
		["git", "/project", "/home/elsewhere/hook.py"],
		["session", "s1", "/home/elsewhere/hook.py"],
	])
})

function sessionClient(configs) {
	return {
		async createSession(config) {
			configs.push(config)
			return { session_id: `s${configs.length}`, config: { model: config.model ?? "mock" } }
		},
		async setModel(sid, body) {
			configs.at(-1).effort = body.reasoning_effort
		},
		async sessions() {
			return { sessions: [] }
		},
		async session(sid) {
			return { session_id: sid, config: { cwd: "." }, events: [] }
		},
		async events() {
			return { events: [] }
		},
		stream() {
			return { close() {}, [Symbol.asyncIterator]: async function* () {} }
		},
	}
}

test("the active preset and custom instructions shape new sessions", async () => {
	const configs = []
	const flow = createFlowStore(sessionClient(configs))
	await flow.newSession()
	assert.equal("system_suffix" in configs[0], false)

	flow.setCustomInstructions("  Be brief.  ")
	const id = flow.savePreset({
		name: "Reviewer",
		tools: ["read", "grep"],
		extensionTools: ["hello"],
		promptMode: "append",
		prompt: "Review for risks.",
	})
	flow.setActivePreset(id)
	await flow.newSession()
	assert.deepEqual(configs[1].tools, ["read", "grep"])
	assert.deepEqual(configs[1].extension_tools, ["hello"])
	assert.equal(configs[1].system_suffix, "Review for risks.\n\nBe brief.")
	assert.equal("system_preamble" in configs[1], false)
	// model, thinking, and approval come from the chat, never the preset
	assert.equal(configs[1].auto_approve, false)
	assert.equal("model" in configs[1], false)
	assert.equal("effort" in configs[1], false)
	assert.equal(configs[1].preset, id) // the chat keeps it, for the settings tab

	flow.savePreset({ ...flow.activePreset(), promptMode: "replace" })
	await flow.newSession()
	assert.equal(configs[2].system_preamble, "Review for risks.")
	assert.equal(configs[2].system_suffix, "Be brief.")

	flow.deletePreset(id)
	assert.equal(flow.state.prefs.activePreset, null)
	await flow.newSession()
	assert.equal("tools" in configs[3], false)
	assert.equal("extension_tools" in configs[3], false)
	assert.equal(configs[3].system_suffix, "Be brief.")
	assert.equal("preset" in configs[3], false)

	// a preset saves where randomUUID is missing, as on plain http to a LAN address
	const randomUUID = Object.getOwnPropertyDescriptor(crypto, "randomUUID")
	Object.defineProperty(crypto, "randomUUID", { value: undefined, configurable: true })
	let other
	try {
		other = flow.savePreset({ name: "Review", tools: ["read"] })
	} finally {
		if (randomUUID) Object.defineProperty(crypto, "randomUUID", randomUUID)
		else delete crypto.randomUUID // the prototype's shows through again
	}
	assert.ok(other)
	assert.deepEqual(
		flow.state.presets.map((preset) => preset.id),
		[other],
	)
})

test("the Default preset adds bundled and extension tools on top of the core tools", async () => {
	const configs = []
	const client = {
		...sessionClient(configs),
		async tools() {
			return {
				tools: [
					{ name: "bash", extension: null, bundled: false },
					{ name: "read", extension: null, bundled: false },
					{ name: "grep", extension: null, bundled: true },
					{ name: "hello", extension: "hello", bundled: false },
					{ name: "read", extension: "sandbox", bundled: false }, // overrides the built-in
				],
			}
		},
	}
	const flow = createFlowStore(client)
	await flow.refreshTools()
	assert.equal(flow.defaultPreset(), null) // nothing ticked: the daemon's own defaults
	await flow.newSession()
	assert.equal("tools" in configs[0], false)
	assert.equal("extension_tools" in configs[0], false)

	// the extension's read unticked: the built-in stays in
	flow.saveDefaultPreset({ tools: ["bash", "read", "grep"], extensionTools: [] })
	assert.deepEqual(flow.state.prefs.defaultPreset, { tools: ["grep"], extensionTools: [] }) // only what sits on top of the core
	assert.deepEqual(flow.defaultPreset(), { tools: ["bash", "read", "grep"], extensionTools: [] })
	await flow.newSession()
	assert.deepEqual(configs[1].tools, ["bash", "read", "grep"])
	assert.deepEqual(configs[1].extension_tools, [])
	assert.equal("preset" in configs[1], false) // not a saved preset

	// a core tool the daemon adds later is on without a re-save
	flow.state.tools.push({ name: "agent", extension: null, bundled: false })
	assert.deepEqual(flow.defaultPreset().tools, ["bash", "read", "agent", "grep"])

	// no tool list to build on: the daemon's defaults, never a chat without its core tools
	flow.state.tools = []
	await flow.newSession()
	assert.equal("tools" in configs[2], false)

	// a send right after page load waits for the tool list instead of dropping the picks
	let listTools
	client.tools = () => new Promise((resolve) => (listTools = resolve))
	flow.refreshTools()
	const creating = flow.newSession()
	listTools({ tools: [{ name: "bash", extension: null, bundled: false }, { name: "grep", extension: null, bundled: true }] })
	await creating
	assert.deepEqual(configs[3].tools, ["bash", "grep"])

	// reloading extensions refetches the tool list
	client.reloadExtensions = async () => ({ extensions: [{ name: "hello" }], diagnostics: [] })
	client.tools = async () => ({ tools: [{ name: "hello", description: "Say hi", extension: "hello" }] })
	await flow.reloadExtensions()
	assert.deepEqual(flow.state.tools, [{ name: "hello", description: "Say hi", extension: "hello" }])
})

function hostClient(calls) {
	return {
		async createSession(config) {
			calls.push(["create", config])
			return { session_id: "s1", config: { model: "mock" } }
		},
		async sessions() {
			return { sessions: [] }
		},
		async session() {
			return { session_id: "s1", model: "mock", latest_seq: 0 }
		},
		async entries() {
			return { entries: [], latest_seq: 0 }
		},
		async run(sid, message) {
			calls.push(["run", message])
			return { status: "ok" }
		},
		stream() {
			return { close() {}, async *[Symbol.asyncIterator]() {} }
		},
	}
}

test("a host can disable all skill catalog requests", async () => {
	const client = hostClient([])
	let requests = 0
	client.skills = client.previewSkills = async () => {
		requests++
		return { skills: [{ name: "review" }] }
	}
	const flow = createFlowStore(client, { skillsEnabled: false })
	await flow.loadSkills()
	await flow.openSession("s1")
	await flow.loadSkills({ force: true })
	assert.equal(requests, 0)
	assert.deepEqual(flow.state.skills, [])
	flow.detach()
})

test("a first message's new chat keeps its bubble, folder and file tabs while it loads", async () => {
	const client = hostClient([])
	client.readFile = async (cwd, path) => ({ path, content: "x" })
	// a model the host no longer offers, so it made the chat with its own
	client.createSession = async (config) => ({ session_id: "s1", config: { model: "agent/default", cwd: config.cwd } })
	const models = []
	client.setModel = async (sid, body) => {
		models.push(body.model)
		return body
	}
	let seeding
	const seeded = new Promise((resolve) => (seeding = resolve))
	let release
	const held = new Promise((resolve) => (release = resolve))
	client.entries = async () => {
		seeding()
		await held
		return { entries: [], latest_seq: 0 }
	}
	const flow = createFlowStore(client)
	flow.state.prefs.lastModel = "retired/model"
	flow.state.prefs.lastEffort = "high"
	flow.setCwd("/project")
	await flow.openFile("/project/a.py")

	const sent = flow.send("count the todos")
	await seeded

	// the new session's transcript is still loading behind the bubble
	assert.equal(flow.state.sessionId, "s1")
	assert.equal(flow.state.session?.config?.cwd, "/project")
	assert.equal(flow.state.conversation.sending.length, 1)
	release()
	assert.equal(await sent, true)
	assert.equal(flow.state.conversation.sending.length, 1)
	assert.equal(flow.state.workspace.open, true)
	assert.deepEqual(flow.state.workspace.tabs.map((tab) => tab.path), ["/project/a.py"])
	// the saved thinking level is set on the model the chat was made with
	assert.deepEqual(models, ["agent/default"])
	flow.detach()
})

test("a first message needs a project folder, unless the host has no filesystem; a host that runs only the models it lists flags another; a daemon's workspaces give a new chat one", async () => {
	const refused = []
	const flow = createFlowStore(hostClient(refused))
	assert.equal(await flow.send("hello"), false)
	assert.deepEqual(refused, [])
	assert.match(flow.state.toast.message, /project folder/)

	const calls = []
	const hostless = createFlowStore(hostClient(calls), { requireCwd: false })
	assert.equal(await hostless.send("hello"), true)
	assert.equal("cwd" in calls[0][1], false)
	assert.deepEqual(calls[1], ["run", "hello"])
	hostless.detach()

	// a host that runs only the models it lists warns of another before anything is sent
	const strict = createFlowStore(hostClient([]), { requireCwd: false, onlyListedModels: true })
	strict.state.models = [{ name: "GPT-4o mini" }]
	strict.state.prefs.lastModel = "GPT-4o"
	assert.match(strict.modelWarning(), /^GPT-4o isn't available/)
	strict.state.prefs.lastModel = "GPT-4o mini"
	assert.equal(strict.modelWarning(), null)
	strict.detach()

	// the first list waits for the workspaces, which the daemon makes as it first lists them; a
	// blank chat then starts in the latest
	const asked = []
	const client = hostClient([])
	let folders = [
		{ path: "/w/shop", name: "Shop" },
		{ path: "/docs/default-workspace", name: "default-workspace" },
	]
	client.workspaces = async () => {
		await null
		asked.push("workspaces")
		return { workspaces: folders }
	}
	client.sessions = async () => {
		asked.push("sessions")
		return {
			sessions: [
				{ session_id: "b", cwd: "/w/gone", workspace: null },
				{ session_id: "a", cwd: "/w/shop", workspace: "/w/shop" },
			],
		}
	}
	client.removeWorkspace = async (path) => {
		folders = folders.filter((folder) => folder.path !== path)
		return { status: "removed" }
	}
	const kept = createFlowStore(client)
	await kept.refreshSessions()
	assert.deepEqual(asked, ["workspaces", "sessions"])
	assert.equal(kept.state.prefs.cwd, "/w/shop")
	assert.deepEqual([kept.folderName("/w/shop"), kept.folderName("/w/gone")], ["Shop", "gone"])

	// a folder picked stands, through another new chat too; with none, a new chat leaves a chat in
	// no workspace for the latest one
	kept.startNewChat({ cwd: "/w/gone" })
	kept.startNewChat()
	assert.equal(kept.state.prefs.cwd, "/w/gone")
	kept.state.sessionId = "b"
	kept.state.session = { config: { cwd: "/w/gone" } }
	kept.startNewChat()
	assert.equal(kept.state.prefs.cwd, "/w/shop")

	// a list still on its way when a workspace is renamed doesn't undo the rename
	let land
	client.workspaces = () => new Promise((resolve) => (land = () => resolve({ workspaces: folders })))
	client.renameWorkspace = async (path, name) => ({ workspace: { path, name } })
	const listing = kept.refreshSessions()
	await kept.renameFolder("/w/shop", "Store")
	land()
	await listing
	assert.equal(kept.folderName("/w/shop"), "Store")

	// a deleted workspace's chats are in none, and a new chat about to start there moves on, until
	// none is left to move to
	await kept.removeFolder("/w/shop")
	assert.equal(kept.state.sessions.find((session) => session.session_id === "a").workspace, null)
	assert.equal(kept.state.prefs.cwd, "/docs/default-workspace")
	await kept.removeFolder("/docs/default-workspace")
	assert.equal(kept.state.prefs.cwd, null)
	assert.equal(await kept.send("hello"), false)
	kept.detach()
})

test("saved state lives under the host's storage key and keeps only what differs from the defaults, an old saved theme moves to frappe-ui's, and a daemon that keeps settings has the last change from either side", async (t) => {
	const backing = new Map()
	const previousStorage = globalThis.localStorage
	globalThis.localStorage = {
		getItem: (key) => backing.get(key) ?? null,
		setItem: (key, value) => backing.set(key, value),
	}
	try {
		const flow = createFlowStore({}, { storageKey: "flow.ui:site:user" })
		flow.setSidebarOpen(false)
		flow.setFolderOpen("/w/app", true)
		flow.setFolderOpen("/w/api", true)
		flow.setFolderOpen("/w/app", false)
		flow.setSidebarView({ sidebarOrder: "manual", chatOrder: ["s2", "s1"] })
		// the chat text size starts at 15px, steps only within its bounds and keeps two decimals
		assert.equal(flow.state.prefs.chatFontSize, 15)
		flow.setChatFontSize(30)
		assert.equal(flow.state.prefs.chatFontSize, 22)
		flow.setChatFontSize(4)
		assert.equal(flow.state.prefs.chatFontSize, 12)
		flow.setChatFontSize(15.01 + 1) // 16.009999999999998
		flow.setChatFontWeight(500)
		const saved = JSON.parse(backing.get("flow.ui:site:user.prefs"))
		assert.equal(saved.chatFontSize, 16.01)
		assert.equal(saved.chatFontWeight, 500)
		assert.equal(saved.sidebarOpen, false)
		assert.deepEqual(saved.openFolders, ["/w/api"])
		assert.deepEqual([saved.sidebarOrder, saved.chatOrder], ["manual", ["s2", "s1"]])
		// a setting at its default isn't kept, so it follows a new default
		assert.equal("sidebarGroup" in saved || "mode" in saved, false)
		assert.equal(backing.has("flow.ui.prefs"), false)

		// the theme used to live in the default key's prefs
		backing.set("flow.ui.prefs", JSON.stringify({ theme: "dark", mode: "auto" }))
		const defaults = createFlowStore({})
		assert.equal(backing.get("theme"), "dark")
		assert.equal("theme" in defaults.state.prefs, false)
		assert.equal(JSON.parse(backing.get("flow.ui.prefs")).theme, undefined)
		assert.equal(defaults.state.prefs.mode, "auto")

		// on first use the daemon gets this browser's settings, but not its window's layout
		t.mock.timers.enable({ apis: ["setTimeout"] })
		const settled = () => new Promise((resolve) => setImmediate(resolve))
		const daemon = { settings: null, saves: [], away: false }
		const client = {
			async settings() {
				return { settings: daemon.settings }
			},
			async updateSettings(changed) {
				if (daemon.away) throw new Error("connection refused")
				daemon.saves.push(Object.keys(changed))
				daemon.settings = { ...daemon.settings, ...changed }
			},
		}
		const scheme = (value) => {
			const colorScheme = ref(value)
			return { colorScheme, setColorScheme: (next) => (colorScheme.value = next) }
		}
		const first = createFlowStore(client, { storageKey: "flow.ui:site:user", colorScheme: scheme("dark") })
		await settled()
		assert.deepEqual(
			[daemon.settings.chatFontSize, daemon.settings.chatOrder, daemon.settings.theme, daemon.settings.presets],
			[16.01, ["s2", "s1"], "dark", []],
		)
		assert.equal("openFolders" in daemon.settings || "sidebarOpen" in daemon.settings, false)
		// a change follows a moment later, alone
		first.setChatFontSize(18)
		first.setSidebarWidth(300)
		t.mock.timers.tick(500)
		await settled()
		assert.deepEqual(daemon.saves.at(-1), ["chatFontSize"])

		// another browser shows the daemon's settings, and keeps its own presets beside the daemon's
		first.savePreset({ name: "Reviewer", tools: ["read"] })
		t.mock.timers.tick(500)
		await settled()
		backing.set("flow.ui:other.presets", JSON.stringify([{ id: "mine", name: "Mine", tools: [] }]))
		const otherScheme = scheme("system")
		const other = createFlowStore(client, { storageKey: "flow.ui:other", colorScheme: otherScheme })
		await settled()
		assert.deepEqual([other.state.prefs.chatFontSize, other.state.prefs.sidebarOrder, otherScheme.colorScheme.value], [18, "manual", "dark"])
		assert.deepEqual(daemon.settings.presets.map((preset) => preset.name), ["Reviewer", "Mine"])
		assert.deepEqual(daemon.saves.at(-1), ["presets"])

		// a change the daemon missed goes to it at the next load, over the copy it has
		daemon.away = true
		other.setChatFontWeight(300)
		t.mock.timers.tick(500)
		await settled()
		daemon.away = false
		first.setChatFontSize(20)
		t.mock.timers.tick(500)
		await settled()
		const reloaded = createFlowStore(client, { storageKey: "flow.ui:other", colorScheme: otherScheme })
		await settled()
		assert.deepEqual([reloaded.state.prefs.chatFontWeight, reloaded.state.prefs.chatFontSize], [300, 20])
		assert.equal(daemon.settings.chatFontWeight, 300)

		// a setting put back to its default goes as null, so every browser follows the default again
		reloaded.setChatFontWeight(450)
		t.mock.timers.tick(500)
		await settled()
		assert.equal(daemon.settings.chatFontWeight, null)
		assert.equal("chatFontWeight" in JSON.parse(backing.get("flow.ui:other.prefs")), false)
		const firstAgain = createFlowStore(client, { storageKey: "flow.ui:site:user", colorScheme: scheme("dark") })
		await settled()
		assert.equal(firstAgain.state.prefs.chatFontWeight, 450)
		assert.equal("chatFontWeight" in JSON.parse(backing.get("flow.ui:site:user.prefs")), false)
	} finally {
		globalThis.localStorage = previousStorage
	}
})

test("attachment previews come from the client when it serves them", async () => {
	const withBlobs = createFlowStore({
		async attachmentBlob(sid, id) {
			assert.equal(sid, "s1")
			assert.equal(id, "att-1")
			return new Blob(["png"])
		},
	})
	const url = await withBlobs.attachmentPreview("s1", "att-1")
	assert.match(url, /^blob:/)
	URL.revokeObjectURL(url)

	const failing = createFlowStore({
		async attachmentBlob() {
			throw new Error("gone")
		},
	})
	assert.equal(await failing.attachmentPreview("s1", "att-1"), null)
	assert.equal(failing.state.toast, null)

	const without = createFlowStore({})
	assert.equal(await without.attachmentPreview("s1", "att-1"), null)
})

// a stream that yields events one at a time when the test says so
function pacedStream(steps) {
	return {
		close() {},
		async *[Symbol.asyncIterator]() {
			for (const { gate, event, delivered } of steps) {
				await gate
				yield event
				delivered()
			}
		},
	}
}

function step(event) {
	let open
	let delivered
	const gate = new Promise((resolve) => (open = resolve))
	const done = new Promise((resolve) => (delivered = resolve))
	return { gate, event, delivered, open, done }
}

const settle = () => new Promise((resolve) => setImmediate(resolve))
const running = async () => ({ entries: [{ type: "run_started", seq: 1 }], latest_seq: 1 })

test("waiting messages go one per run that ran its course; a pause, stop or denial holds them", async () => {
	const calls = []
	const paused = step({ type: "run_ended", seq: 2, reason: "paused" })
	const resumed = step({ type: "run_started", seq: 3 })
	const done = step({ type: "run_ended", seq: 4, reason: "done" })
	const second = step({ type: "run_started", seq: 5 })
	const echo = step({ type: "user_message", seq: 6, content: "Also check this" })
	const aborted = step({ type: "run_ended", seq: 7, reason: "aborted" })
	const third = step({ type: "run_started", seq: 8 })
	const denied = step({ type: "run_ended", seq: 9, reason: "denied" })
	const client = hostClient(calls)
	client.entries = running
	client.abort = async () => calls.push(["abort"])
	client.stream = () => pacedStream([paused, resumed, done, second, echo, aborted, third, denied])
	const flow = createFlowStore(client)
	await flow.openSession("s1")
	const queued = () => flow.state.queued.map((item) => item.label)
	const play = async (...steps) => {
		for (const each of steps) each.open()
		await steps.at(-1).done
		await settle()
	}

	assert.equal(await flow.send("Also check this"), true)
	assert.equal(await flow.send("And this"), true)
	assert.deepEqual(calls, []) // nothing reaches the server mid-run
	assert.equal(flow.state.conversation.sending.length, 0)
	assert.deepEqual(queued(), ["Also check this", "And this"])

	// a run paused for approval keeps its queue until the run finishes
	await play(paused)
	assert.deepEqual(calls, [])

	// one message per finished run: the next waits for the turn this one opens
	await play(resumed, done)
	assert.deepEqual(calls, [["run", "Also check this"]])
	assert.equal(flow.state.conversation.sending.length, 1)
	assert.deepEqual(queued(), ["And this"])

	// a stopped run leaves its queue waiting, to send by hand
	await play(second, echo)
	await flow.abort()
	await play(aborted)
	assert.deepEqual(calls.slice(1), [["abort"]])
	assert.deepEqual(queued(), ["And this"])
	await flow.sendQueued(flow.state.queued[0])
	assert.deepEqual(calls.slice(1), [["abort"], ["run", "And this"]])
	assert.deepEqual(flow.state.queued, [])
	assert.equal(flow.state.conversation.sending.length, 1)

	// a denied tool call leaves the queue waiting, like a stop
	await play(third)
	await flow.send("One more")
	await play(denied)
	assert.equal(calls.length, 3)
	assert.deepEqual(queued(), ["One more"])
	flow.detach()
})

test("a message sent while the last one is on its way waits for that run, even across a chat switch", async () => {
	const calls = []
	const client = hostClient(calls)
	// the last run ended on its own before either message was sent
	client.entries = async () => ({
		entries: [{ type: "run_started", seq: 1 }, { type: "run_ended", seq: 2, reason: "done" }],
		latest_seq: 2,
	})
	let answer
	client.run = (sid, message) => {
		calls.push(["run", message])
		return new Promise((resolve) => (answer = resolve))
	}
	const flow = createFlowStore(client)
	await flow.openSession("s1")
	const queued = () => flow.state.queued.map((item) => item.label)

	const first = flow.send("First")
	await settle()
	assert.equal(await flow.send("Second"), true)
	assert.deepEqual(calls, [["run", "First"]])
	assert.deepEqual(queued(), ["Second"])

	// reopened before the first's run shows up in its transcript, the chat keeps the second waiting
	await flow.openSession("s2")
	await flow.openSession("s1")
	await settle()
	answer({ status: "started" })
	assert.equal(await first, true)
	assert.deepEqual(calls, [["run", "First"]])
	assert.deepEqual(queued(), ["Second"])
	flow.detach()
})

test("a steered message waits as a bubble below the turn until its echo, however its files come back", async () => {
	const echo = step({ type: "user_message", seq: 2, content: "Also check this" })
	// after a reload, /flow names an inlined file by name and lists it after the rest
	const echoFiles = step({
		type: "user_message",
		seq: 3,
		content: [
			{ type: "text", text: "Use these" },
			{ type: "attachment", id: "D7", name: "shot.png", kind: "image" },
			{ type: "attachment", id: "file:notes.txt", name: "notes.txt", kind: "file" },
		],
	})
	const calls = []
	const client = hostClient(calls)
	client.entries = running
	let answer
	client.run = (sid, message, ids) => {
		// the turn can take a steer before run() answers: its bubble holds the ids the echo matches on
		calls.push(["run", message, ids, [...flow.state.conversation.steering.at(-1).attachmentIds]])
		return new Promise((resolve) => (answer = resolve))
	}
	client.stream = () => pacedStream([echo, echoFiles])
	const flow = createFlowStore(client)
	await flow.openSession("s1")
	const steering = () => flow.state.conversation.steering.map((item) => item.text)

	await flow.send("Also check this")
	const steered = flow.sendQueued(flow.state.queued[0])
	// the bubble is up before the server answers
	assert.deepEqual(flow.state.queued, [])
	assert.deepEqual(steering(), ["Also check this"])
	await settle()
	answer({ status: "steered" })
	await steered
	assert.deepEqual(steering(), ["Also check this"])
	assert.equal(flow.state.conversation.sending.length, 0)
	echo.open()
	await echo.done
	assert.deepEqual(steering(), [])

	const files = [
		{ id: "F1", name: "notes.txt", kind: "file" },
		{ id: "F2", name: "shot.png", kind: "image" },
	]
	await flow.send("Use these", files)
	const withFiles = flow.sendQueued(flow.state.queued[0])
	await settle()
	answer({ status: "steered" })
	await withFiles
	assert.deepEqual(steering(), ["Use these"])
	echoFiles.open()
	await echoFiles.done
	assert.deepEqual(steering(), [])
	assert.deepEqual(calls, [
		["run", "Also check this", [], []],
		["run", "Use these", ["F1", "F2"], ["F1", "F2"]],
	])
	flow.detach()
})

test("a steer the turn never took goes when the turn ends; a pause keeps it for the resumed turn", async () => {
	for (const [reason, left] of [
		["denied", 0],
		["budget", 0],
		["max_turns", 0],
		["paused", 1],
	]) {
		const ended = step({ type: "run_ended", seq: 2, reason })
		const client = hostClient([])
		client.entries = running
		client.run = async () => ({ status: "steered" })
		client.stream = () => pacedStream([ended])
		const flow = createFlowStore(client)
		await flow.openSession("s1")

		await flow.send("Also check this")
		await flow.sendQueued(flow.state.queued[0])
		assert.equal(flow.state.conversation.steering.length, 1, reason)
		ended.open()
		await ended.done
		assert.equal(flow.state.conversation.steering.length, left, reason)
		flow.detach()
	}
})

test("the server decides whether a message steered or opened a turn, and its bubble follows once", async () => {
	for (const [busy, text, status, echo, steering, sending] of [
		// a steer the server turned into a turn of its own (the run had ended unheard) gets its bubble
		[true, "Next question", "started", false, [], 1],
		// no second bubble when the echo lands before the run answers
		[true, "Next question", "started", true, [], 0],
		// no steered bubble when a run this tab had not heard of takes the message first
		[false, "Next question", "steered", true, [], 0],
		// a multiline skill waits under the expanded event's canonical match key
		[false, "/skill:review\n\ncheck auth", "steered", false, ["/skill:review check auth"], 0],
	]) {
		const label = `${busy ? "queued" : "sent"}, ${status}${echo ? ", echoed first" : ""}`
		const client = hostClient([])
		if (busy) client.entries = running
		client.run = async () => {
			if (echo) applyEvent(flow.state.conversation, { type: "user_message", seq: 2, content: text })
			return { status }
		}
		const flow = createFlowStore(client)
		await flow.openSession("s1")

		assert.equal(await flow.send(text), true, label)
		if (busy) await flow.sendQueued(flow.state.queued[0])
		assert.deepEqual(flow.state.queued, [], label)
		assert.deepEqual(flow.state.conversation.steering.map((item) => item.text), steering, label)
		assert.equal(flow.state.conversation.sending.length, sending, label)
		assert.equal(flow.state.conversation.entries.length, echo ? 1 : 0, label)
		flow.detach()
	}
})

test("a waiting message the run can't take now waits again in its own chat's queue", async () => {
	const calls = []
	const client = hostClient(calls)
	client.entries = running
	let fail
	client.run = (sid, message) => {
		calls.push(["run", message])
		return new Promise((resolve, reject) => (fail = reject))
	}
	const flow = createFlowStore(client)
	await flow.openSession("s1")
	await flow.send("Also check this")
	const queued = () => flow.state.queued.map((item) => item.label)

	// nothing is sent or steered past an unanswered approval
	flow.state.conversation.pendingApproval = { seq: 2, calls: [{ id: "c1" }], answers: {} }
	assert.equal(await flow.send("just use the create tool"), false)
	assert.equal(flow.state.toast.kind, "error")
	flow.state.toast = null
	await flow.sendQueued(flow.state.queued[0])
	assert.equal(flow.state.toast.kind, "error")
	assert.deepEqual(calls, [])
	assert.equal(flow.state.conversation.sending.length, 0)
	assert.deepEqual(queued(), ["Also check this"])
	flow.state.conversation.pendingApproval = null

	// a steer that fails to reach the server waits in the queue again
	flow.state.toast = null
	const steered = flow.sendQueued(flow.state.queued[0])
	await settle()
	fail(new Error("offline"))
	await steered
	assert.equal(flow.state.toast.kind, "error")
	assert.deepEqual(flow.state.conversation.steering, [])
	assert.deepEqual(queued(), ["Also check this"])

	// one that fails after a chat switch waits again in its own chat
	const again = flow.sendQueued(flow.state.queued[0])
	await settle()
	await flow.openSession("s2")
	fail(new Error("offline"))
	await again
	assert.deepEqual(flow.state.queued, [])
	await flow.openSession("s1")
	assert.deepEqual(queued(), ["Also check this"])
	flow.detach()
})

test("a waiting message holds staged files: taken back it drops them, and it outlives a reload", async (t) => {
	const saved = new Map()
	globalThis.sessionStorage = { getItem: (key) => saved.get(key) ?? null, setItem: (key, value) => saved.set(key, value) }
	t.after(() => delete globalThis.sessionStorage)
	const calls = []
	const client = hostClient(calls)
	client.entries = running
	client.uploadAttachments = async (sid, files) => {
		calls.push(["upload", files.map((file) => file.name)])
		return { attachments: [{ id: "A1", name: "shot.png", kind: "image" }] }
	}
	client.cleanupAttachments = async (sid, ids) => calls.push(["cleanup", sid, ids])
	client.run = async (sid, message, ids) => {
		calls.push(["run", message, ids])
		return { status: "ok" }
	}
	const flow = createFlowStore(client)
	await flow.openSession("s1")

	// taken back, it is never sent; the server keeps any file an earlier message holds, so every id goes
	await flow.send("Use these", [{ id: "F1", file: { name: "a.png" } }, { id: "F2", name: "b.pdf" }])
	flow.removeQueued(flow.state.queued[0])
	await flow.send("Look at this", [{ key: "k1", name: "shot.png", kind: "image", file: { name: "shot.png" } }])
	await settle()
	flow.detach()

	// the reload: a new store in the same tab, the run still going
	const ended = step({ type: "run_ended", seq: 2, reason: "done" })
	client.stream = () => pacedStream([ended])
	const again = createFlowStore(client)
	await again.openSession("s1")
	assert.deepEqual(
		again.state.queued.map((item) => item.label),
		["Look at this"],
	)

	ended.open()
	await ended.done
	await settle()
	assert.deepEqual(calls, [
		["cleanup", "s1", ["F1", "F2"]],
		["upload", ["shot.png"]],
		["run", "Look at this", ["A1"]],
	])
	assert.deepEqual(again.state.queued, [])
	again.detach()
})

test("a message whose files finish going up after its run ended goes out at once, or waits after a stop", async () => {
	for (const [reason, sent, waiting] of [
		["done", [["run", "Look at this"]], []],
		["aborted", [], ["Look at this"]],
	]) {
		const calls = []
		const ended = step({ type: "run_ended", seq: 2, reason })
		const client = hostClient(calls)
		client.entries = running
		client.stream = () => pacedStream([ended])
		let uploaded
		client.uploadAttachments = () => new Promise((resolve) => (uploaded = resolve))
		const flow = createFlowStore(client)
		await flow.openSession("s1")

		const sending = flow.send("Look at this", [{ key: "k1", name: "shot.png", kind: "image", file: { name: "shot.png" } }])
		await settle()
		ended.open()
		await ended.done
		uploaded({ attachments: [{ id: "A1", name: "shot.png", kind: "image" }] })
		assert.equal(await sending, true, reason)
		assert.deepEqual(calls, sent, reason)
		assert.deepEqual(
			flow.state.queued.map((item) => item.label),
			waiting,
			reason,
		)
		flow.detach()
	}
})

test("waiting messages wait with their own chat, and go when it reopens on a run that ran its course", async () => {
	for (const [reason, sent, waiting] of [
		["done", [["run", "Also check this"]], ["Look at this"]],
		["aborted", [], ["Also check this", "Look at this"]],
	]) {
		const calls = []
		const client = hostClient(calls)
		let end = null
		client.entries = async () => ({
			entries: [{ type: "run_started", seq: 1 }, ...(end ? [{ type: "run_ended", seq: 2, reason: end }] : [])],
			latest_seq: end ? 2 : 1,
		})
		let uploaded
		client.uploadAttachments = () => new Promise((resolve) => (uploaded = resolve))
		const flow = createFlowStore(client)
		await flow.openSession("s1")
		await flow.send("Also check this")

		// one whose files go up while another chat opens waits with its own
		const sending = flow.send("Look at this", [{ key: "k1", name: "shot.png", kind: "image", file: { name: "shot.png" } }])
		await settle()
		await flow.openSession("s2")
		assert.deepEqual(flow.state.queued, [], reason)
		uploaded({ attachments: [{ id: "A1", name: "shot.png", kind: "image" }] })
		assert.equal(await sending, true, reason)
		assert.deepEqual(flow.state.queued, [], reason)
		flow.startNewChat()
		assert.deepEqual(flow.state.queued, [], reason)

		end = reason // the run ends while another chat is open
		await flow.openSession("s1")
		await settle()
		assert.deepEqual(calls, sent, reason)
		assert.deepEqual(
			flow.state.queued.map((item) => item.label),
			waiting,
			reason,
		)
		flow.detach()
	}
})

test("the open session's row follows its live run boundaries and title, over a list served before them", async () => {
	const started = step({ type: "run_started", seq: 2, run_id: "r1" })
	const paused = step({ type: "run_ended", seq: 3, reason: "paused" })
	const resumed = step({ type: "run_started", seq: 4, run_id: "r2" })
	const ended = step({ type: "run_ended", seq: 5, reason: "done" })
	const titled = step({ type: "title_changed", title: "Read Aadhaar PDF" })
	const lists = []
	const client = {
		sessions: () => new Promise((resolve) => lists.push(resolve)),
		async session() {
			return { session_id: "s1", model: "m", latest_seq: 1 }
		},
		async entries() {
			return { entries: [], latest_seq: 1 }
		},
		stream() {
			return pacedStream([started, paused, resumed, ended, titled])
		},
	}
	const flow = createFlowStore(client)
	await flow.openSession("s1")
	const rows = () => flow.state.sessions.map((s) => [s.session_id, s.state])
	// served before the title and the run's end landed
	const served = () => ({
		sessions: [
			{ session_id: "s0", title: "Older", state: "idle" },
			{ session_id: "s1", title: "read this", state: "running" },
		],
	})

	// a session the list doesn't know yet is fetched on its first run boundary
	started.open()
	await started.done
	assert.equal(lists.length, 1)
	lists[0](served())
	await settle()
	assert.deepEqual(rows(), [
		["s0", "idle"],
		["s1", "running"],
	])

	// a live boundary moves its row to the top without refetching the list
	paused.open()
	await paused.done
	assert.deepEqual(rows(), [
		["s1", "paused"],
		["s0", "idle"],
	])
	assert.equal(lists.length, 1)

	// a list served before live events landed doesn't undo them on the open session's row
	const refresh = flow.refreshSessions()
	resumed.open()
	ended.open()
	titled.open()
	await titled.done
	assert.equal(flow.state.session.title, "Read Aadhaar PDF")
	lists[1](served())
	await refresh
	const open = flow.state.sessions.find((s) => s.session_id === "s1")
	assert.equal(flow.sessionTitle(open), "Read Aadhaar PDF")
	assert.equal(open.state, "idle")
	flow.detach()
})

function subagentSeed() {
	return [
		{ type: "run_started", seq: 1, run_id: "r1" },
		{ type: "user_message", seq: 2, content: "go" },
		{
			type: "assistant_message",
			seq: 3,
			content: [{ type: "tool_call", id: "c1", name: "subagent", arguments: { task: "count", description: "count beans" } }],
		},
		{ type: "run_started", seq: 4, run_id: "r2", subagent_id: "c1" },
		{ type: "user_message", seq: 5, content: "count", subagent_id: "c1" },
	]
}

test("a sub-agent opens as a workspace tab that survives a refresh and follows the branch", async () => {
	const backing = new Map()
	const previousStorage = globalThis.localStorage
	globalThis.localStorage = {
		getItem: (key) => backing.get(key) ?? null,
		setItem: (key, value) => backing.set(key, value),
	}
	try {
		let entries = subagentSeed()
		let reads = 0
		const client = {
			session: async () => ({ session_id: "s1", latest_seq: 5, config: { cwd: "/proj" }, model: "mock" }),
			entries: async () => ({ entries, latest_seq: 5 }),
			readFile: async (cwd, path) => (reads++, { path, content: "hello" }),
			stream: () => ({ close() {}, async *[Symbol.asyncIterator]() {} }),
		}
		const flow = createFlowStore(client)
		await flow.openSession("s1")
		flow.openSubagent("c1")
		assert.deepEqual(flow.state.workspace.tabs, [{ kind: "subagent", path: "c1", name: "Sub-agent: count beans" }])
		assert.equal(flow.state.workspace.active, "c1")
		assert.equal(flow.state.workspace.open, true)
		flow.openSubagent("c1") // again: the same tab
		assert.equal(flow.state.workspace.tabs.length, 1)
		flow.selectFile("c1")
		await new Promise((resolve) => setTimeout(resolve, 0))
		assert.equal(reads, 0) // nothing to fetch for a thread

		// a fresh store (page refresh) restores the tab and names it from the loaded thread
		const restored = createFlowStore(client)
		await restored.openSession("s1")
		assert.deepEqual(restored.state.workspace.tabs, [{ kind: "subagent", path: "c1", name: "Sub-agent: count beans" }])
		assert.equal(restored.state.workspace.active, "c1")

		// a rewind past the call reloads the same session; the child is off the branch now
		entries = entries.slice(0, 2)
		await restored.openSession("s1")
		assert.deepEqual(restored.state.workspace.tabs, [])
		assert.equal(restored.state.workspace.open, false)
	} finally {
		globalThis.localStorage = previousStorage
	}
})

test("a sub-agent's batch is answered with its own seq, and auto-approve answers every sub-agent waiting", async () => {
	const resumes = []
	const client = {
		async patchConfig() {
			return { config: { auto_approve: true } }
		},
		async resume(sessionId, seq, answers) {
			resumes.push({ seq, answers })
			return { status: "resumed" }
		},
	}
	const flow = createFlowStore(client)
	flow.state.sessionId = "s1"
	const conversation = flow.state.conversation
	for (const event of subagentSeed()) applyEvent(conversation, event)
	const ask = (seq, id, subagent_id) =>
		applyEvent(conversation, {
			type: "approval_required",
			seq,
			calls: [{ id, name: "bash", args: { command: "ls" } }],
			subagent_id,
		})
	ask(6, "a1", "c1")
	applyEvent(conversation, { type: "run_ended", seq: 7, reason: "paused", subagent_id: "c1" })
	applyEvent(conversation, { type: "run_started", seq: 8, run_id: "r3", subagent_id: "c9" })
	ask(9, "b1", "c9")
	applyEvent(conversation, { type: "run_started", seq: 10, run_id: "r4", subagent_id: "c7" })
	ask(11, "d1", "c7")

	// the card answers the oldest batch while the session runs
	await flow.answerApproval("a1", "Approve")
	assert.deepEqual(resumes, [{ seq: 6, answers: { a1: "Approve" } }])

	// auto-approve answers every one still waiting, not just the oldest
	await flow.setMode("auto")
	assert.deepEqual(resumes.slice(1), [
		{ seq: 9, answers: { b1: "Approve" } },
		{ seq: 11, answers: { d1: "Approve" } },
	])
})

test("a quote queues once; clearing takes what was sent, or everything", () => {
	const flow = createFlowStore({})
	flow.addQuote("stale row")
	flow.addQuote("stale row")
	flow.addQuote("pins the list")
	assert.deepEqual(flow.state.quotes, ["stale row", "pins the list"])
	flow.removeQuote(0)
	assert.deepEqual(flow.state.quotes, ["pins the list"])
	flow.addQuote("stale row")
	flow.clearQuotes(["pins the list"])
	assert.deepEqual(flow.state.quotes, ["stale row"])
	flow.clearQuotes()
	assert.deepEqual(flow.state.quotes, [])

	flow.state.session = { config: { cwd: "/w" } }
	flow.addCodeRef("/w/a.py", 1, 2)
	flow.addCodeRef("a.py", 1, 2) // a rewound token, the same lines
	flow.addCodeRef("/w/b.py", 3, 3)
	flow.clearCodeRefs([flow.state.codeRefs[0]])
	assert.deepEqual(flow.state.codeRefs.map((ref) => ref.path), ["/w/b.py"])
	flow.clearCodeRefs()
	assert.deepEqual(flow.state.codeRefs, [])
})

test("a new chat's first message goes to the chat made for it, wherever the user goes meanwhile", async () => {
	const calls = []
	const client = hostClient(calls)
	const created = []
	client.createSession = () => new Promise((resolve) => created.push(resolve))
	let release
	const held = new Promise((resolve) => (release = resolve))
	client.session = async (sid) => {
		if (sid === "B") await held
		return { session_id: sid, model: "mock", latest_seq: 0 }
	}
	client.run = async (sid, message) => {
		calls.push(["run", sid, message])
		return { status: "ok" }
	}
	const flow = createFlowStore(client, { requireCwd: false })

	// a message from another new chat while the first's chat is created gets a chat of its own,
	// and the first's chat doesn't open over the one the user is on
	const first = flow.send("first")
	await settle()
	flow.startNewChat()
	const second = flow.send("second")
	await settle()
	created[0]({ session_id: "A", config: { model: "mock" } })
	assert.equal(await first, true)
	assert.equal(flow.state.sessionId, null)

	// a chat the user opens while the second's chat loads stays open
	created[1]?.({ session_id: "B", config: { model: "mock" } })
	await settle()
	await flow.openSession("C")
	release()
	assert.equal(await second, true)
	assert.deepEqual(calls, [
		["run", "A", "first"],
		["run", "B", "second"],
	])
	assert.equal(flow.state.sessionId, "C")
	flow.detach()
})

test("/rewind passes over a message steered into a run and takes the run's own message", async () => {
	const rewinds = []
	const client = hostClient([])
	const text = (value) => [{ type: "text", text: value }]
	client.entries = async () => ({
		entries: [
			{ type: "run_started", seq: 1, parent_seq: 0, run_id: "r1" },
			{ type: "user_message", seq: 2, parent_seq: 1, content: "start" },
			{ type: "assistant_message", seq: 3, parent_seq: 2, content: text("reply-1") },
			{ type: "user_message", seq: 4, parent_seq: 3, content: "steer me" },
			{ type: "assistant_message", seq: 5, parent_seq: 4, content: text("reply-2") },
			{ type: "run_ended", seq: 6, parent_seq: 5, reason: "done" },
		],
		latest_seq: 6,
	})
	client.rewind = async (sid, target) => {
		rewinds.push([sid, target])
		return { status: "rewound" }
	}
	const flow = createFlowStore(client)
	await flow.openSession("s1")

	assert.deepEqual(flow.state.conversation.steeredSeqs, [4])
	assert.equal(await flow.rewindLastUserMessage(), "start")
	assert.deepEqual(rewinds, [["s1", 0]])
	flow.detach()
})

test("a compaction takes steering away as soon as it's asked for; a refused one gives it back", async () => {
	let refuse
	const client = hostClient([])
	client.compact = () => new Promise((resolve, reject) => (refuse = reject))
	const flow = createFlowStore(client)
	await flow.openSession("s1")

	const asked = flow.compact()
	assert.equal(flow.state.conversation.compacting, "manual")
	refuse(new FlowAPIError(409, "a run is already active"))
	await asked
	assert.equal(flow.state.conversation.compacting, false)
	flow.detach()
})
