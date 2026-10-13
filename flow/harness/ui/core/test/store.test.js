import assert from "node:assert/strict"
import test from "node:test"

import { FlowAPIError } from "../src/client.js"
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
		["", "t1"],
	])
})

test("a prepared attachment is sent by id without uploading it again", async () => {
	const calls = []
	const client = {
		async run(sid, text, ids) { calls.push([sid, text, ids]); return {} },
		async uploadAttachments() { assert.fail("Already prepared") },
	}
	const flow = createFlowStore(client)
	flow.state.sessionId = "s1"
	assert.equal(await flow.send("Read this", [{ id: "F1", file: { name: "notes.pdf" } }]), true)
	assert.deepEqual(calls, [["s1", "Read this", ["F1"]]])
})

test("skill completion previews the catalog without creating a session", async () => {
	let previews = 0
	const client = {
		async previewSkills(config) {
			previews += 1
			assert.equal(config.cwd, "/project")
			return { skills: [{ name: "review", description: "Review changes" }] }
		},
	}
	const flow = createFlowStore(client)
	flow.setCwd("/project")

	await Promise.all([flow.loadSkills(), flow.loadSkills()])

	assert.equal(previews, 1)
	assert.equal(flow.state.sessionId, null)
	assert.deepEqual(flow.state.skills, [{ name: "review", description: "Review changes" }])
})

test("an open session refetches its skills only when forced", async () => {
	let skills = [{ name: "review", description: "Review changes" }]
	let fetches = 0
	const client = {
		async session() {
			return { session_id: "s1", model: "m", latest_seq: 1 }
		},
		async entries() {
			return { entries: [], latest_seq: 1 }
		},
		async skills(sid) {
			fetches += 1
			assert.equal(sid, "s1")
			return { skills }
		},
		stream() {
			return { close() {}, async *[Symbol.asyncIterator]() {} }
		},
	}
	const flow = createFlowStore(client)
	await flow.openSession("s1")
	assert.equal(fetches, 1)

	// a skill written after the session started is invocable, so it reaches the list
	skills = [...skills, { name: "testing", description: "Added later" }]
	await flow.loadSkills()
	assert.equal(fetches, 1)
	assert.deepEqual(flow.state.skills.map((skill) => skill.name), ["review"])

	await flow.loadSkills({ force: true })

	assert.equal(fetches, 2)
	assert.deepEqual(flow.state.skills.map((skill) => skill.name), ["review", "testing"])
	flow.detach()
})

test("a forced skill refetch is not overwritten by an older response", async () => {
	const requests = []
	const client = {
		async session() {
			return { session_id: "s1", model: "m", latest_seq: 1 }
		},
		async entries() {
			return { entries: [], latest_seq: 1 }
		},
		skills() {
			return new Promise((resolve) => requests.push(resolve))
		},
		stream() {
			return { close() {}, async *[Symbol.asyncIterator]() {} }
		},
	}
	const flow = createFlowStore(client)
	const opened = flow.openSession("s1")
	requests[0]({ skills: [{ name: "old" }] })
	await opened

	const stale = flow.loadSkills({ force: true })
	const fresh = flow.loadSkills({ force: true })
	requests[2]({ skills: [{ name: "new" }] })
	await fresh
	requests[1]({ skills: [{ name: "old" }] })
	await stale

	assert.deepEqual(
		flow.state.skills.map((skill) => skill.name),
		["new"],
	)
	flow.detach()
})

test("skill previews do not reuse a request from another working directory", async () => {
	const requests = []
	const client = {
		previewSkills(config) {
			let resolve
			const promise = new Promise((done) => (resolve = done))
			requests.push({ cwd: config.cwd, resolve })
			return promise
		},
	}
	const flow = createFlowStore(client)
	flow.setCwd("/first")
	const first = flow.loadSkills()
	flow.setCwd("/second")
	const second = flow.loadSkills()

	requests[0].resolve({ skills: [{ name: "first" }] })
	await first
	assert.equal(requests[1].cwd, "/second")
	assert.deepEqual(flow.state.skills, [])

	requests[1].resolve({ skills: [{ name: "second" }] })
	await second
	assert.deepEqual(flow.state.skills, [{ name: "second" }])
})

test("new chats inherit the active session cwd and accept a project override", () => {
	const flow = createFlowStore({})
	flow.state.sessions = [{ session_id: "session-1", cwd: "/projects/active" }]
	flow.state.sessionId = "session-1"

	flow.startNewChat()
	assert.equal(flow.state.prefs.cwd, "/projects/active")

	flow.startNewChat({ cwd: "/projects/selected" })
	assert.equal(flow.state.prefs.cwd, "/projects/selected")
})

test("the model list is marked loading while models are fetched", async () => {
	let answer
	const flow = createFlowStore({ models: () => new Promise((resolve) => (answer = resolve)) })
	const refresh = flow.refreshModels()
	assert.equal(flow.state.modelsLoading, true)
	answer({ models: [{ name: "a/b", provider: "a" }] })
	await refresh
	assert.equal(flow.state.modelsLoading, false)
	assert.equal(flow.state.models.length, 1)
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

test("a chat being opened waits for its own model, and an effort picked meanwhile changes no model", async () => {
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
})

test("a host whose list carries the current model shows it while a chat opens, and keeps that row current", async () => {
	let respond, answerModel
	const client = {
		session: () => new Promise((resolve) => (respond = resolve)),
		async entries() {
			return { entries: [], latest_seq: 1 }
		},
		setModel: () => new Promise((resolve) => (answerModel = resolve)),
		stream() {
			return { close() {}, async *[Symbol.asyncIterator]() {} }
		},
	}
	const flow = createFlowStore(client, { listedModel: true })
	flow.state.sessions = [
		{ session_id: "a", model: "m/a" },
		{ session_id: "b", model: "m/b" },
	]
	const opened = flow.openSession("a")
	assert.equal(flow.state.conversation.model, "m/a")
	respond({ session_id: "a", model: "m/a", latest_seq: 1 })
	await opened

	// a model change that lands after a switch belongs to the chat it was made in
	const changed = flow.selectModel("m/new")
	const switched = flow.openSession("b")
	respond({ session_id: "b", model: "m/b", latest_seq: 1 })
	await switched
	answerModel({ model: "m/new" })
	await changed
	assert.deepEqual(
		flow.state.sessions.map((s) => s.model),
		["m/new", "m/b"],
	)
	assert.equal(flow.state.conversation.model, "m/b")
	flow.detach()
})

test("reopening the chat that is already open keeps it loading until the reload lands", async () => {
	let respond
	const client = {
		session: () => new Promise((resolve) => (respond = resolve)),
		async entries() {
			return { entries: [], latest_seq: 1 }
		},
		// a live stream stays open until it is closed
		stream() {
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
	const opened = flow.openSession("s1")
	respond({ session_id: "s1", model: "m", latest_seq: 1 })
	await opened

	const reopened = flow.openSession("s1")
	await new Promise((resolve) => setImmediate(resolve)) // the old stream winds down
	assert.equal(flow.state.loading, true)
	respond({ session_id: "s1", model: "m", latest_seq: 1 })
	await reopened
	assert.equal(flow.state.loading, false)
	flow.detach()
})

test("a thinking level that lands after a switch stays with the chat it was picked in", async () => {
	let respond, answer
	const client = {
		session: () => new Promise((resolve) => (respond = resolve)),
		async entries() {
			return { entries: [], latest_seq: 1 }
		},
		setModel: () => new Promise((resolve) => (answer = resolve)),
		stream() {
			return { close() {}, async *[Symbol.asyncIterator]() {} }
		},
	}
	const flow = createFlowStore(client)
	const opened = flow.openSession("a")
	respond({ session_id: "a", model: "m/a", latest_seq: 1 })
	await opened

	const picked = flow.selectEffort("high")
	const switched = flow.openSession("b")
	respond({ session_id: "b", model: "m/b", latest_seq: 1 })
	await switched
	answer({ model: "m/a", reasoning_effort: "high" })
	await picked
	assert.equal(flow.state.conversation.reasoningEffort, null)
	flow.detach()
})

test("a new chat started while a session loads is not left loading", async () => {
	let respond
	const client = {
		session: () => new Promise((resolve) => (respond = resolve)),
		async entries() {
			return { entries: [], latest_seq: 1 }
		},
	}
	const flow = createFlowStore(client)
	const opened = flow.openSession("s1")
	assert.equal(flow.state.loading, true)

	flow.startNewChat()
	assert.equal(flow.state.loading, false)
	respond({ session_id: "s1", model: "m", latest_seq: 1 })
	await opened
	assert.equal(flow.state.loading, false)
	assert.equal(flow.state.sessionId, null)
})

test("multiline skill steering uses the expanded event's canonical match key", async () => {
	const client = {
		async run() {
			return { status: "steered" }
		},
	}
	const flow = createFlowStore(client)
	flow.state.sessionId = "session-1"

	assert.equal(await flow.send("/skill:review\n\ncheck auth"), true)
	assert.equal(flow.state.conversation.steering[0].text, "/skill:review check auth")
})

test("send() resolves @-mention paths into attachments before running", async () => {
	const attachCalls = []
	const runCalls = []
	const client = {
		async attachFiles(sid, paths) {
			attachCalls.push({ sid, paths })
			return { attachments: paths.map((path, i) => ({ id: `att-${i}`, name: path })) }
		},
		async run(sid, message, attachments) {
			runCalls.push({ sid, message, attachments })
			return { status: "ok" }
		},
	}
	const flow = createFlowStore(client)
	flow.state.sessionId = "session-1"

	const sent = await flow.send("check this file", [
		{ key: "mention:0", name: "foo.py", kind: "file", mentionPath: "src/foo.py" },
	])

	assert.equal(sent, true)
	assert.deepEqual(attachCalls, [{ sid: "session-1", paths: ["src/foo.py"] }])
	assert.deepEqual(runCalls[0].attachments, ["att-0"])
})

test("a run that fails after resolving a mention cleans up the newly created attachment", async () => {
	const cleaned = []
	const client = {
		async attachFiles() {
			return { attachments: [{ id: "att-0", name: "foo.py" }] }
		},
		async run() {
			throw new Error("boom")
		},
		async cleanupAttachments(sid, attachments) {
			cleaned.push({ sid, attachments })
		},
	}
	const flow = createFlowStore(client)
	flow.state.sessionId = "session-1"

	const sent = await flow.send("check this file", [
		{ key: "mention:0", name: "foo.py", kind: "file", mentionPath: "src/foo.py" },
	])

	assert.equal(sent, false)
	assert.deepEqual(cleaned, [{ sid: "session-1", attachments: ["att-0"] }])
})

test("send() resolves an upload and a mention concurrently, not sequentially", async () => {
	let uploadFinished = false
	let mentionRanBeforeUploadFinished = false
	const client = {
		async uploadAttachments() {
			await new Promise((resolve) => setTimeout(resolve, 10))
			uploadFinished = true
			return { attachments: [{ id: "att-upload" }] }
		},
		async attachFiles() {
			// sequential code awaits uploadAttachments to completion first, so this
			// would only ever see uploadFinished === true if the two aren't parallel
			if (!uploadFinished) mentionRanBeforeUploadFinished = true
			return { attachments: [{ id: "att-mention" }] }
		},
		async run(sid, message, attachments) {
			return { status: "ok", attachments }
		},
	}
	const flow = createFlowStore(client)
	flow.state.sessionId = "session-1"

	const sent = await flow.send("check these", [
		{ key: "local:0", name: "screen.png", kind: "image", file: {} },
		{ key: "mention:0", name: "foo.py", kind: "file", mentionPath: "src/foo.py" },
	])

	assert.equal(sent, true)
	assert.equal(mentionRanBeforeUploadFinished, true)
})

test("uploads and mentions share one cap, checked before anything is staged", async () => {
	// each staging endpoint caps at MAX_ATTACHMENTS on its own, so 6 + 6 passes both
	// and only the combined run payload is oversized — catch it before staging.
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
	const flow = createFlowStore(client)
	flow.state.sessionId = "session-1"

	const attachments = [
		...Array.from({ length: 6 }, (_, i) => ({ key: `local:${i}`, kind: "image", file: {} })),
		...Array.from({ length: 6 }, (_, i) => ({ key: `mention:${i}`, kind: "file", mentionPath: `f${i}.py` })),
	]
	assert.equal(attachments.length, MAX_ATTACHMENTS + 2)

	const sent = await flow.send("too many", attachments)

	assert.equal(sent, false)
	assert.deepEqual(calls, []) // nothing staged, so nothing to clean up
	assert.match(flow.state.toast.message, /at most 10 attachments/)
})

test("a failed upload still queues cleanup for an already-resolved mention attachment", async () => {
	const cleaned = []
	const client = {
		async uploadAttachments() {
			throw new Error("upload failed")
		},
		async attachFiles() {
			return { attachments: [{ id: "att-mention" }] }
		},
		async cleanupAttachments(sid, attachments) {
			cleaned.push({ sid, attachments })
		},
	}
	const flow = createFlowStore(client)
	flow.state.sessionId = "session-1"

	const sent = await flow.send("check these", [
		{ key: "local:0", name: "screen.png", kind: "image", file: {} },
		{ key: "mention:0", name: "foo.py", kind: "file", mentionPath: "src/foo.py" },
	])

	assert.equal(sent, false)
	assert.deepEqual(cleaned, [{ sid: "session-1", attachments: ["att-mention"] }])
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

test("denying one call in a batch denies the undecided rest and resumes", async () => {
	const resumes = []
	const flow = approvalStore(resumes)

	await flow.answerApproval("c1", "Deny")

	assert.deepEqual(resumes, [{ seq: 7, answers: { c1: "Deny", c2: "Deny" } }])
})

test("a deny keeps earlier explicit answers", async () => {
	const resumes = []
	const flow = approvalStore(resumes)

	await flow.answerApproval("c1", "Approve")
	assert.equal(resumes.length, 0) // still waiting on c2

	await flow.answerApproval("c2", "Deny")
	assert.deepEqual(resumes, [{ seq: 7, answers: { c1: "Approve", c2: "Deny" } }])
})

test("an approve alone still waits for the rest of the batch", async () => {
	const resumes = []
	const flow = approvalStore(resumes)

	await flow.answerApproval("c1", "Approve")

	assert.equal(resumes.length, 0)
})

test("successful model selection replaces the header context window", async () => {
	const client = {
		async setModel(sessionId, selection) {
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

	await flow.selectModel("deepseek/deepseek-chat")

	assert.equal(flow.state.conversation.model, "deepseek/deepseek-chat")
	assert.equal(flow.state.conversation.contextWindow, 1_000_000)
	assert.equal(flow.state.session.context_window, 1_000_000)
})

test("session replay restores the selected model's limit after a trailing model change", async () => {
	const client = {
		async session() {
			return {
				session_id: "session-1",
				model: "deepseek/deepseek-chat",
				reasoning_effort: null,
				context_tokens: 5_000,
				context_window: 1_000_000,
				latest_seq: 1,
			}
		},
		async entries() {
			return {
				entries: [{ type: "model_changed", seq: 1, model: "deepseek/deepseek-chat" }],
				latest_seq: 1,
			}
		},
		stream() {
			return {
				close() {},
				async *[Symbol.asyncIterator]() {},
			}
		},
	}
	const flow = createFlowStore(client)

	await flow.openSession("session-1")

	assert.equal(flow.state.conversation.model, "deepseek/deepseek-chat")
	assert.equal(flow.state.conversation.contextWindow, 1_000_000)
	flow.detach()
})

test("refresh restores the in-progress assistant prefix before continuing live", async () => {
	let releaseSuffix
	let prefixDelivered
	let suffixDelivered
	const suffixGate = new Promise((resolve) => (releaseSuffix = resolve))
	const sawPrefix = new Promise((resolve) => (prefixDelivered = resolve))
	const sawSuffix = new Promise((resolve) => (suffixDelivered = resolve))
	const client = {
		async session() {
			return { session_id: "s1", model: "mock", running: true, latest_seq: 2 }
		},
		async entries() {
			return {
				entries: [
					{ type: "run_started", seq: 1, run_id: "r1" },
					{ type: "user_message", seq: 2, content: "write a story" },
				],
				latest_seq: 2,
			}
		},
		stream(sid, since) {
			assert.equal(sid, "s1")
			assert.equal(since, 2)
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
	await sawPrefix
	assert.deepEqual(flow.state.conversation.partial, [{ type: "text", text: "prefix" }])
	assert.deepEqual(flow.state.conversation.entries.map((entry) => entry.type), ["user_message"])

	releaseSuffix()
	await sawSuffix
	assert.deepEqual(flow.state.conversation.partial, [{ type: "text", text: "prefix suffix" }])
	flow.detach()
})

test("workspace tabs persist per session and restore after a refresh", async () => {
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
			readFile: async (cwd, path) => ({ path, content: "hello" }),
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
		await new Promise((resolve) => setTimeout(resolve, 0))
		assert.equal(restored.state.workspace.tabs[0].content, "hello") // active tab hydrated

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

test("diff tabs load the git diff for the browsed cwd, even before a session", async () => {
	const calls = []
	const client = {
		async gitFileDiff(cwd, path) {
			calls.push([cwd, path])
			return { path, original: "old\n", modified: "new\n" }
		},
	}
	const flow = createFlowStore(client)
	flow.setCwd("/project")

	await flow.openDiffFile("/project/app.py")

	assert.deepEqual(calls, [["/project", "/project/app.py"]])
	const tab = flow.state.workspace.tabs[0]
	assert.equal(tab.diff, true)
	assert.equal(tab.original, "old\n")
	assert.equal(tab.content, "new\n")
	assert.equal(flow.state.workspace.open, true)
})

test("git change polling swallows errors instead of toasting", async () => {
	const flow = createFlowStore({
		async gitChanges() {
			throw new Error("boom")
		},
	})
	flow.setCwd("/project")

	assert.equal(await flow.gitChanges(), null)
	assert.equal(flow.state.toast, null)
})

test("diff tabs fall back to the session diff for files outside the repository", async () => {
	const calls = []
	const client = {
		async gitFileDiff() {
			calls.push("git")
			throw new FlowAPIError(400, "file is outside the repository")
		},
		async fileDiff(sid, path) {
			calls.push(["session", sid, path])
			return { path, original: "before\n", modified: "after\n" }
		},
	}
	const flow = createFlowStore(client)
	flow.state.sessionId = "s1"
	flow.state.session = { config: { cwd: "/project" } }

	await flow.openDiffFile("/home/elsewhere/hook.py")

	assert.deepEqual(calls, ["git", ["session", "s1", "/home/elsewhere/hook.py"]])
	const tab = flow.state.workspace.tabs[0]
	assert.equal(tab.error, null)
	assert.equal(tab.original, "before\n")
	assert.equal(tab.content, "after\n")
})

test("files save against the browsed cwd even before a session", async () => {
	const calls = []
	const client = {
		async readFile(cwd, path) {
			return { path, content: "old" }
		},
		async writeFsFile(cwd, path, content) {
			calls.push([cwd, path, content])
			return { path }
		},
	}
	const flow = createFlowStore(client)
	flow.setCwd("/project")
	await flow.openFile("/project/a.txt")

	assert.equal(await flow.saveFile("/project/a.txt", "new"), true)
	assert.deepEqual(calls, [["/project", "/project/a.txt", "new"]])
	assert.equal(flow.state.workspace.tabs[0].content, "new")
})

test("custom instructions travel as system_suffix on new sessions", async () => {
	const configs = []
	const client = {
		async createSession(config) {
			configs.push(config)
			return { session_id: "s1", config: { model: "mock" } }
		},
		async sessions() {
			return { sessions: [] }
		},
		async session() {
			return { session_id: "s1", config: { cwd: "." }, events: [] }
		},
		async events() {
			return { events: [] }
		},
		stream() {
			return { close() {}, [Symbol.asyncIterator]: async function* () {} }
		},
	}
	const flow = createFlowStore(client)
	await flow.newSession()
	flow.setCustomInstructions("  Reply tersely.  ")
	await flow.newSession()

	assert.equal("system_suffix" in configs[0], false)
	assert.equal(configs[1].system_suffix, "Reply tersely.")
})

test("a theme saved in the old prefs moves to frappe-ui's storage key", () => {
	const previousStorage = globalThis.localStorage
	const stored = { "flow.ui.prefs": JSON.stringify({ theme: "dark", mode: "auto" }) }
	globalThis.localStorage = {
		getItem: (key) => stored[key] ?? null,
		setItem: (key, value) => (stored[key] = value),
	}
	try {
		const flow = createFlowStore({})
		assert.equal(stored.theme, "dark")
		assert.equal("theme" in flow.state.prefs, false)
		assert.equal(JSON.parse(stored["flow.ui.prefs"]).theme, undefined)
		assert.equal(flow.state.prefs.mode, "auto")
	} finally {
		globalThis.localStorage = previousStorage
	}
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

test("the active preset shapes new sessions and joins the custom instructions", async () => {
	const configs = []
	const flow = createFlowStore(sessionClient(configs))
	flow.setCustomInstructions("Be brief.")
	const id = flow.savePreset({
		name: "Reviewer",
		tools: ["read", "grep"],
		extensionTools: ["hello"],
		promptMode: "append",
		prompt: "Review for risks.",
	})
	flow.setActivePreset(id)
	await flow.newSession()
	assert.deepEqual(configs[0].tools, ["read", "grep"])
	assert.deepEqual(configs[0].extension_tools, ["hello"])
	assert.equal(configs[0].system_suffix, "Review for risks.\n\nBe brief.")
	assert.equal("system_preamble" in configs[0], false)
	// model, thinking, and approval come from the chat, never the preset
	assert.equal(configs[0].auto_approve, false)
	assert.equal("model" in configs[0], false)
	assert.equal("effort" in configs[0], false)
	assert.equal(flow.state.sessionPresets.s1, id) // remembered per chat, for the settings tab

	flow.savePreset({ ...flow.activePreset(), promptMode: "replace" })
	await flow.newSession()
	assert.equal(configs[1].system_preamble, "Review for risks.")
	assert.equal(configs[1].system_suffix, "Be brief.")

	flow.deletePreset(id)
	assert.equal(flow.state.prefs.activePreset, null)
	assert.equal("s1" in flow.state.sessionPresets, false) // the chat's record goes with the preset
	await flow.newSession()
	assert.equal("tools" in configs[2], false)
	assert.equal("extension_tools" in configs[2], false)
	assert.equal(configs[2].system_suffix, "Be brief.")
	assert.equal("s3" in flow.state.sessionPresets, false)
})

test("the Default preset adds bundled and extension tools on top of the core tools", async () => {
	const configs = []
	const client = {
		...sessionClient(configs),
		async tools() {
			return {
				tools: [
					{ name: "bash", extension: null, bundled: false },
					{ name: "grep", extension: null, bundled: true },
					{ name: "hello", extension: "hello", bundled: false },
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

	flow.saveDefaultPreset({ tools: ["bash", "grep"], extensionTools: [] })
	assert.deepEqual(flow.state.prefs.defaultPreset, { tools: ["grep"], extensionTools: [] }) // only what sits on top of the core
	assert.deepEqual(flow.defaultPreset(), { tools: ["bash", "grep"], extensionTools: [] })
	await flow.newSession()
	assert.deepEqual(configs[1].tools, ["bash", "grep"])
	assert.deepEqual(configs[1].extension_tools, [])
	assert.equal("s2" in flow.state.sessionPresets, false) // not a saved preset

	// a core tool the daemon adds later is on without a re-save
	flow.state.tools.push({ name: "agent", extension: null, bundled: false })
	assert.deepEqual(flow.defaultPreset().tools, ["bash", "agent", "grep"])

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
})

test("a built-in stays in the Default tools while an extension overrides it", async () => {
	const configs = []
	const client = {
		...sessionClient(configs),
		async tools() {
			return {
				tools: [
					{ name: "read", extension: null, bundled: false },
					{ name: "read", extension: "sandbox", bundled: false },
				],
			}
		},
	}
	const flow = createFlowStore(client)
	await flow.refreshTools()
	flow.saveDefaultPreset({ tools: ["read"], extensionTools: [] }) // the extension's read unticked
	await flow.newSession()
	assert.deepEqual(configs[0].tools, ["read"])
	assert.deepEqual(configs[0].extension_tools, [])
})

test("reloading extensions refetches the tool list", async () => {
	const client = {
		async reloadExtensions() {
			return { extensions: [{ name: "hello" }], diagnostics: [] }
		},
		async tools() {
			return { tools: [{ name: "hello", description: "Say hi", extension: "hello" }] }
		},
	}
	const flow = createFlowStore(client)
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

test("the first message keeps its bubble while its session is created", async () => {
	const client = hostClient([])
	let seeding
	const seeded = new Promise((resolve) => (seeding = resolve))
	let release
	const held = new Promise((resolve) => (release = resolve))
	client.entries = async () => {
		seeding()
		await held
		return { entries: [], latest_seq: 0 }
	}
	const flow = createFlowStore(client, { requireCwd: false })

	const sent = flow.send("count the todos")
	await seeded

	// the new session's transcript is still loading behind the bubble
	assert.equal(flow.state.conversation.sending.length, 1)
	release()
	assert.equal(await sent, true)
	assert.equal(flow.state.conversation.sending.length, 1)
	flow.detach()
})

test("the folder stays in the header while the first message's session loads", async () => {
	const client = hostClient([])
	client.createSession = async (config) => ({ session_id: "s1", config: { model: "mock", cwd: config.cwd } })
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
	flow.setCwd("/project")

	const sent = flow.send("count the todos")
	await seeded

	assert.equal(flow.state.sessionId, "s1")
	assert.equal(flow.state.session?.config?.cwd, "/project")
	release()
	assert.equal(await sent, true)
	flow.detach()
})

test("a host without a filesystem sends without choosing a folder", async () => {
	const calls = []
	const flow = createFlowStore(hostClient(calls), { requireCwd: false })

	assert.equal(await flow.send("hello"), true)

	assert.equal("cwd" in calls[0][1], false)
	assert.deepEqual(calls[1], ["run", "hello"])
	flow.detach()
})

test("the default store still refuses to send without a folder", async () => {
	const calls = []
	const flow = createFlowStore(hostClient(calls))

	assert.equal(await flow.send("hello"), false)

	assert.deepEqual(calls, [])
	assert.match(flow.state.toast.message, /project folder/)
})

test("saved state lives under the host's storage key", () => {
	const backing = new Map()
	const previousStorage = globalThis.localStorage
	globalThis.localStorage = {
		getItem: (key) => backing.get(key) ?? null,
		setItem: (key, value) => backing.set(key, value),
	}
	try {
		const flow = createFlowStore({}, { storageKey: "flow.ui:site:user" })
		flow.setSidebarOpen(false)
		assert.equal(JSON.parse(backing.get("flow.ui:site:user.prefs")).sidebarOpen, false)
		assert.equal(backing.has("flow.ui.prefs"), false)

		const defaults = createFlowStore({})
		defaults.setSidebarOpen(false)
		assert.equal(backing.has("flow.ui.prefs"), true)
		assert.deepEqual(defaults.options, {
			requireCwd: true,
			storageKey: "flow.ui",
			maxAttachments: MAX_ATTACHMENTS,
			skillsEnabled: true,
			workspace: true,
			presentTool: null,
		})
	} finally {
		globalThis.localStorage = previousStorage
	}
})

test("the attachment cap follows the host's option", async () => {
	const calls = []
	const flow = createFlowStore(hostClient(calls), { maxAttachments: 2 })
	flow.state.sessionId = "s1"

	const attachments = Array.from({ length: 3 }, (_, i) => ({ key: `local:${i}`, kind: "image", file: {} }))
	assert.equal(await flow.send("too many", attachments), false)

	assert.deepEqual(calls, [])
	assert.match(flow.state.toast.message, /at most 2 attachments/)
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

test("a message sent during a run waits for it to end, then opens the next turn", async () => {
	const calls = []
	const ended = step({ type: "run_ended", seq: 2, reason: "done" })
	const client = hostClient(calls)
	client.entries = running
	client.stream = () => pacedStream([ended])
	const flow = createFlowStore(client)
	await flow.openSession("s1")

	assert.equal(await flow.send("Also check this"), true)
	assert.equal(await flow.send("And this"), true)
	assert.deepEqual(calls, []) // nothing reaches the server mid-run
	assert.equal(flow.state.conversation.sending.length, 0)
	assert.deepEqual(
		flow.state.queued.map((item) => item.label),
		["Also check this", "And this"],
	)

	// one message per finished run: the next waits for the turn this one opens
	ended.open()
	await ended.done
	await settle()
	assert.deepEqual(calls, [["run", "Also check this"]])
	assert.equal(flow.state.conversation.sending.length, 1)
	assert.deepEqual(
		flow.state.queued.map((item) => item.label),
		["And this"],
	)
	flow.detach()
})

test("a message sent while the last one is on its way waits for that run", async () => {
	const calls = []
	const client = hostClient(calls)
	const flow = createFlowStore(client)
	await flow.openSession("s1")
	// only the first run hangs, so a second one reaching the server fails the test
	let answer
	client.run = (sid, message) => {
		calls.push(["run", message])
		if (answer) return Promise.resolve({ status: "steered" })
		return new Promise((resolve) => (answer = resolve))
	}

	const first = flow.send("Do this")
	await settle()
	assert.equal(await flow.send("And then this"), true)
	answer({ status: "started" })
	await first
	assert.deepEqual(calls, [["run", "Do this"]])
	assert.deepEqual(
		flow.state.queued.map((item) => item.label),
		["And then this"],
	)
	flow.detach()
})

test("a run paused for approval keeps its queue until the run finishes", async () => {
	const calls = []
	const paused = step({ type: "run_ended", seq: 2, reason: "paused" })
	const resumed = step({ type: "run_started", seq: 3 })
	const done = step({ type: "run_ended", seq: 4, reason: "done" })
	const client = hostClient(calls)
	client.entries = running
	client.stream = () => pacedStream([paused, resumed, done])
	const flow = createFlowStore(client)
	await flow.openSession("s1")

	await flow.send("Also check this")
	paused.open()
	await paused.done
	await settle()
	assert.deepEqual(calls, [])

	resumed.open()
	done.open()
	await done.done
	await settle()
	assert.deepEqual(calls, [["run", "Also check this"]])
	flow.detach()
})

test("a stopped run leaves its queue waiting, to send by hand", async () => {
	const calls = []
	const ended = step({ type: "run_ended", seq: 2, reason: "aborted" })
	const client = hostClient(calls)
	client.entries = running
	client.abort = async () => calls.push(["abort"])
	client.stream = () => pacedStream([ended])
	const flow = createFlowStore(client)
	await flow.openSession("s1")

	await flow.send("Also check this")
	await flow.abort()
	ended.open()
	await ended.done
	await settle()
	assert.deepEqual(calls, [["abort"]])
	assert.deepEqual(
		flow.state.queued.map((item) => item.label),
		["Also check this"],
	)

	await flow.sendQueued(flow.state.queued[0])
	assert.deepEqual(calls, [["abort"], ["run", "Also check this"]])
	assert.deepEqual(flow.state.queued, [])
	assert.equal(flow.state.conversation.sending.length, 1)
	flow.detach()
})

test("a denied tool call leaves the queue waiting, like a stop", async () => {
	const calls = []
	const ended = step({ type: "run_ended", seq: 2, reason: "denied" })
	const client = hostClient(calls)
	client.entries = running
	client.stream = () => pacedStream([ended])
	const flow = createFlowStore(client)
	await flow.openSession("s1")

	await flow.send("Also check this")
	ended.open()
	await ended.done
	await settle()
	assert.deepEqual(calls, [])
	assert.deepEqual(
		flow.state.queued.map((item) => item.label),
		["Also check this"],
	)
	flow.detach()
})

test("a steered message leaves the queue for a bubble below the turn until the turn takes it", async () => {
	const calls = []
	const echo = step({ type: "user_message", seq: 2, content: "Also check this" })
	const client = hostClient(calls)
	client.entries = running
	let answer
	client.run = (sid, message) => {
		calls.push(["run", message])
		return new Promise((resolve) => (answer = resolve))
	}
	client.stream = () => pacedStream([echo])
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
	assert.deepEqual(calls, [["run", "Also check this"]])
	assert.deepEqual(steering(), ["Also check this"])
	assert.equal(flow.state.conversation.sending.length, 0)

	echo.open()
	await echo.done
	assert.deepEqual(steering(), [])
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

test("a steer the server turned into a turn of its own gets its bubble", async () => {
	const client = hostClient([])
	client.entries = running
	client.run = async () => ({ status: "started" }) // the run had ended; the client had not heard
	const flow = createFlowStore(client)
	await flow.openSession("s1")

	assert.equal(await flow.send("Next question"), true)
	await flow.sendQueued(flow.state.queued[0])
	assert.deepEqual(flow.state.queued, [])
	assert.deepEqual(flow.state.conversation.steering, [])
	assert.equal(flow.state.conversation.sending.length, 1)
	flow.detach()
})

test("no second bubble when the echo lands before the run answers", async () => {
	const client = hostClient([])
	client.entries = running
	client.run = async () => {
		applyEvent(flow.state.conversation, { type: "user_message", seq: 2, content: "Next question" })
		return { status: "started" }
	}
	const flow = createFlowStore(client)
	await flow.openSession("s1")

	assert.equal(await flow.send("Next question"), true)
	await flow.sendQueued(flow.state.queued[0])
	assert.deepEqual(flow.state.conversation.steering, [])
	assert.equal(flow.state.conversation.sending.length, 0)
	flow.detach()
})

test("no steered bubble when a run this tab had not heard of takes the message before the server answers", async () => {
	const client = hostClient([])
	client.run = async () => {
		applyEvent(flow.state.conversation, { type: "user_message", seq: 1, content: "Next question" })
		return { status: "steered" }
	}
	const flow = createFlowStore(client)
	await flow.openSession("s1")

	assert.equal(await flow.send("Next question"), true)
	assert.equal(flow.state.conversation.entries.length, 1)
	assert.deepEqual(flow.state.conversation.steering, [])
	flow.detach()
})

test("a queued steer carries its attachments before the run answers", async () => {
	const client = hostClient([])
	client.entries = running
	let idsWhenAsked = null
	client.run = async (sid, message, ids) => {
		idsWhenAsked = [...(flow.state.conversation.steering[0]?.attachmentIds ?? [])]
		assert.deepEqual(ids, ["F1"])
		return { status: "steered" }
	}
	const flow = createFlowStore(client)
	await flow.openSession("s1")

	assert.equal(await flow.send("Use this one", [{ id: "F1", name: "notes.pdf" }]), true)
	await flow.sendQueued(flow.state.queued[0])
	// the turn can consume the steering before run() answers; the echo matches on these
	assert.deepEqual(idsWhenAsked, ["F1"])
	flow.detach()
})

test("a steer that fails to reach the server waits in the queue again", async () => {
	const client = hostClient([])
	client.entries = running
	client.run = async () => {
		throw new Error("offline")
	}
	const flow = createFlowStore(client)
	await flow.openSession("s1")

	await flow.send("Also check this")
	await flow.sendQueued(flow.state.queued[0])
	assert.equal(flow.state.toast.kind, "error")
	assert.deepEqual(flow.state.conversation.steering, [])
	assert.deepEqual(
		flow.state.queued.map((item) => item.label),
		["Also check this"],
	)
	flow.detach()
})

test("a waiting message is not steered past an unanswered approval", async () => {
	const calls = []
	const client = hostClient(calls)
	client.entries = running
	const flow = createFlowStore(client)
	await flow.openSession("s1")

	await flow.send("Also check this")
	flow.state.conversation.pendingApproval = { seq: 2, calls: [{ id: "c1" }], answers: {} }
	await flow.sendQueued(flow.state.queued[0])
	assert.deepEqual(calls, [])
	assert.equal(flow.state.toast.kind, "error")
	assert.deepEqual(
		flow.state.queued.map((item) => item.label),
		["Also check this"],
	)
	flow.detach()
})

test("a waiting message taken back is never sent, and its staged files go with it", async () => {
	const calls = []
	const ended = step({ type: "run_ended", seq: 2, reason: "done" })
	const client = hostClient(calls)
	client.entries = running
	client.cleanupAttachments = async (sid, ids) => calls.push(["cleanup", sid, ids])
	client.stream = () => pacedStream([ended])
	const flow = createFlowStore(client)
	await flow.openSession("s1")

	// the server keeps any file an earlier message holds, so every id goes
	await flow.send("Use these", [{ id: "F1", file: { name: "a.png" } }, { id: "F2", name: "b.pdf" }])
	flow.removeQueued(flow.state.queued[0])
	ended.open()
	await ended.done
	await settle()
	assert.deepEqual(calls, [["cleanup", "s1", ["F1", "F2"]]])
	assert.deepEqual(flow.state.queued, [])
	flow.detach()
})

test("this tab's waiting messages outlive a reload, their files already uploaded", async (t) => {
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
	const flow = createFlowStore(client)
	await flow.openSession("s1")
	await flow.send("Look at this", [{ key: "k1", name: "shot.png", kind: "image", file: { name: "shot.png" } }])
	await settle()
	flow.detach()

	// the reload: a new store in the same tab, the run still going
	const ended = step({ type: "run_ended", seq: 2, reason: "done" })
	const reloaded = hostClient(calls)
	reloaded.entries = running
	reloaded.stream = () => pacedStream([ended])
	reloaded.run = async (sid, message, ids) => {
		calls.push(["run", message, ids])
		return { status: "ok" }
	}
	const again = createFlowStore(reloaded)
	await again.openSession("s1")
	assert.deepEqual(
		again.state.queued.map((item) => item.label),
		["Look at this"],
	)

	ended.open()
	await ended.done
	await settle()
	assert.deepEqual(calls, [
		["upload", ["shot.png"]],
		["run", "Look at this", ["A1"]],
	])
	again.detach()
})

test("a message whose files finish going up after its run ended goes out at once", async () => {
	const calls = []
	const ended = step({ type: "run_ended", seq: 2, reason: "done" })
	const client = hostClient(calls)
	client.entries = running
	client.stream = () => pacedStream([ended])
	let uploaded
	client.uploadAttachments = () => new Promise((resolve) => (uploaded = resolve))
	const flow = createFlowStore(client)
	await flow.openSession("s1")

	const sent = flow.send("Look at this", [{ key: "k1", name: "shot.png", kind: "image", file: { name: "shot.png" } }])
	await settle()
	ended.open()
	await ended.done
	uploaded({ attachments: [{ id: "A1", name: "shot.png", kind: "image" }] })
	assert.equal(await sent, true)
	assert.deepEqual(calls, [["run", "Look at this"]])
	assert.deepEqual(flow.state.queued, [])
	flow.detach()
})

test("a message whose files finish going up after a stop waits for the user", async () => {
	const calls = []
	const ended = step({ type: "run_ended", seq: 2, reason: "aborted" })
	const client = hostClient(calls)
	client.entries = running
	client.stream = () => pacedStream([ended])
	let uploaded
	client.uploadAttachments = () => new Promise((resolve) => (uploaded = resolve))
	const flow = createFlowStore(client)
	await flow.openSession("s1")

	const sent = flow.send("Look at this", [{ key: "k1", name: "shot.png", kind: "image", file: { name: "shot.png" } }])
	await settle()
	ended.open()
	await ended.done
	uploaded({ attachments: [{ id: "A1", name: "shot.png", kind: "image" }] })
	assert.equal(await sent, true)
	assert.deepEqual(calls, [])
	assert.deepEqual(
		flow.state.queued.map((item) => item.label),
		["Look at this"],
	)
	flow.detach()
})

test("a message whose files go up while another session opens waits with its own", async () => {
	const client = hostClient([])
	client.entries = running
	let uploaded
	client.uploadAttachments = () => new Promise((resolve) => (uploaded = resolve))
	const flow = createFlowStore(client)
	await flow.openSession("s1")

	const sent = flow.send("Look at this", [{ key: "k1", name: "shot.png", kind: "image", file: { name: "shot.png" } }])
	await settle()
	await flow.openSession("s2")
	uploaded({ attachments: [{ id: "A1", name: "shot.png", kind: "image" }] })
	assert.equal(await sent, true)
	assert.deepEqual(flow.state.queued, [])
	await flow.openSession("s1")
	assert.deepEqual(
		flow.state.queued.map((item) => item.label),
		["Look at this"],
	)
	flow.detach()
})

test("waiting messages stay with their session while another is open", async () => {
	const client = hostClient([])
	client.entries = running
	const flow = createFlowStore(client)
	await flow.openSession("s1")
	await flow.send("Also check this")

	await flow.openSession("s2")
	assert.deepEqual(flow.state.queued, [])
	flow.startNewChat()
	assert.deepEqual(flow.state.queued, [])
	await flow.openSession("s1")
	assert.deepEqual(
		flow.state.queued.map((item) => item.label),
		["Also check this"],
	)
	flow.detach()
})

test("a chat reopened after its run ran its course sends the next waiting message; after a stop it waits", async () => {
	for (const [reason, sent] of [
		["done", [["run", "Also check this"]]],
		["aborted", []],
	]) {
		const calls = []
		const client = hostClient(calls)
		let end = null
		client.entries = async () => ({
			entries: [{ type: "run_started", seq: 1 }, ...(end ? [{ type: "run_ended", seq: 2, reason: end }] : [])],
			latest_seq: end ? 2 : 1,
		})
		const flow = createFlowStore(client)
		await flow.openSession("s1")
		await flow.send("Also check this")
		await flow.openSession("s2")
		end = reason // the run ends while another chat is open
		await flow.openSession("s1")
		await settle()
		assert.deepEqual(calls, sent, reason)
		flow.detach()
	}
})

test("a chat reopened before the run of a message on its way shows up keeps the next one waiting", async () => {
	const calls = []
	const client = hostClient(calls)
	// the last run ended on its own before either message was sent
	client.entries = async () => ({
		entries: [{ type: "run_started", seq: 1 }, { type: "run_ended", seq: 2, reason: "done" }],
		latest_seq: 2,
	})
	client.run = (sid, message) => {
		calls.push(["run", message])
		return new Promise(() => {}) // still on its way
	}
	const flow = createFlowStore(client)
	await flow.openSession("s1")

	void flow.send("First")
	await settle()
	assert.equal(await flow.send("Second"), true) // waits for the first's run
	await flow.openSession("s2")
	await flow.openSession("s1") // the first's run is not in the transcript yet
	await settle()
	assert.deepEqual(calls, [["run", "First"]])
	assert.deepEqual(
		flow.state.queued.map((item) => item.label),
		["Second"],
	)
	flow.detach()
})

test("a message waits in the box while an approval is unanswered", async () => {
	const client = hostClient([])
	client.entries = async () => ({
		entries: [{ type: "run_started", seq: 1 }, { type: "run_ended", seq: 2, reason: "paused" }],
		latest_seq: 2,
	})
	client.run = async () => assert.fail("a paused run refuses it anyway")
	const flow = createFlowStore(client)
	await flow.openSession("s1")
	flow.state.conversation.pendingApproval = { seq: 2, calls: [{ id: "c1" }], answers: {} }

	assert.equal(await flow.send("just use the create tool"), false)
	assert.equal(flow.state.toast.kind, "error")
	assert.equal(flow.state.conversation.sending.length, 0)
	assert.deepEqual(flow.state.queued, [])
	flow.detach()
})

test("a message the server did not steer keeps its bubble", async () => {
	const client = hostClient([])
	client.entries = running
	client.run = async () => ({ status: "ok" }) // the run had ended; this opens a turn
	const flow = createFlowStore(client)
	await flow.openSession("s1")

	assert.equal(await flow.send("Next question"), true)
	await flow.sendQueued(flow.state.queued[0])
	assert.deepEqual(flow.state.queued, [])
	flow.detach()
})

test("a live run boundary moves the open session's row to the top without refetching the list", async () => {
	const started = step({ type: "run_started", seq: 2, run_id: "r1" })
	const ended = step({ type: "run_ended", seq: 3, reason: "paused" })
	const client = {
		async sessions() {
			assert.fail("the list is already known")
		},
		async session() {
			return { session_id: "s2", model: "m", latest_seq: 1, state: "idle" }
		},
		async entries() {
			return { entries: [], latest_seq: 1 }
		},
		stream() {
			return pacedStream([started, ended])
		},
	}
	const flow = createFlowStore(client)
	flow.state.sessions = [
		{ session_id: "s1", title: "Older", state: "idle" },
		{ session_id: "s2", title: "Open", state: "idle" },
	]
	await flow.openSession("s2")

	started.open()
	await started.done
	assert.deepEqual(
		flow.state.sessions.map((s) => [s.session_id, s.state]),
		[["s2", "running"], ["s1", "idle"]],
	)

	ended.open()
	await ended.done
	assert.equal(flow.state.sessions[0].state, "paused")
	flow.detach()
})

test("a session the list doesn't know yet is fetched on its first run boundary", async () => {
	const started = step({ type: "run_started", seq: 1, run_id: "r1" })
	let fetches = 0
	const client = {
		async sessions() {
			fetches += 1
			return { sessions: [{ session_id: "s1", title: "read this", state: "running" }] }
		},
		async session() {
			return { session_id: "s1", model: "m", latest_seq: 0 }
		},
		async entries() {
			return { entries: [], latest_seq: 0 }
		},
		stream() {
			return pacedStream([started])
		},
	}
	const flow = createFlowStore(client)
	await flow.openSession("s1")

	started.open()
	await started.done
	await new Promise((resolve) => setTimeout(resolve, 0)) // the fetch is not awaited
	assert.equal(fetches, 1)
	assert.deepEqual(flow.state.sessions.map((s) => [s.session_id, s.state]), [["s1", "running"]])
	flow.detach()
})

test("a list served before live events landed doesn't undo them on the open session's row", async () => {
	const ended = step({ type: "run_ended", seq: 2, reason: "done" })
	const titled = step({ type: "title_changed", title: "Read Aadhaar PDF" })
	let releaseList
	const listServed = new Promise((resolve) => (releaseList = resolve))
	const client = {
		async sessions() {
			await listServed
			return { sessions: [{ session_id: "s1", title: "read this", state: "running" }] }
		},
		async session() {
			return { session_id: "s1", model: "m", latest_seq: 1, title: "read this", state: "running" }
		},
		async entries() {
			return { entries: [], latest_seq: 1 }
		},
		stream() {
			return pacedStream([ended, titled])
		},
	}
	const flow = createFlowStore(client)
	flow.state.sessions = [{ session_id: "s1", title: "read this", state: "running" }]
	await flow.openSession("s1")

	const refresh = flow.refreshSessions() // served now: no title yet, run still on
	ended.open()
	await ended.done
	titled.open()
	await titled.done
	assert.equal(flow.state.session.title, "Read Aadhaar PDF")

	releaseList()
	await refresh
	assert.equal(flow.sessionTitle(flow.state.sessions[0]), "Read Aadhaar PDF")
	assert.equal(flow.state.sessions[0].state, "idle")
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

test("a sub-agent's batch is answered with its own seq while the session runs", async () => {
	const resumes = []
	const client = {
		async resume(sessionId, seq, answers) {
			resumes.push({ seq, answers })
			return { status: "resumed" }
		},
	}
	const flow = createFlowStore(client)
	flow.state.sessionId = "s1"
	for (const event of subagentSeed()) applyEvent(flow.state.conversation, event)
	const calls = [{ id: "c2", name: "bash", args: { command: "rm x" } }]
	applyEvent(flow.state.conversation, { type: "approval_required", seq: 6, calls, subagent_id: "c1" })
	applyEvent(flow.state.conversation, { type: "run_ended", seq: 7, reason: "paused", subagent_id: "c1" })

	await flow.answerApproval("c2", "Approve")
	assert.deepEqual(resumes, [{ seq: 6, answers: { c2: "Approve" } }])
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
