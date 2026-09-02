import assert from "node:assert/strict"
import test from "node:test"

import { FlowAPIError } from "../src/client.js"
import { createFlowStore, MAX_ATTACHMENTS } from "../src/store.js"

globalThis.localStorage = {
	getItem() {
		return null
	},
	setItem() {},
}

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

test("multiline skill steering uses the expanded event's canonical queue key", async () => {
	const client = {
		async run() {
			return { status: "steered" }
		},
	}
	const flow = createFlowStore(client)
	flow.state.sessionId = "session-1"

	assert.equal(await flow.send("/skill:review\n\ncheck auth"), true)
	assert.equal(flow.state.queued[0].text, "/skill:review check auth")
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
		tools: ["read_file", "grep"],
		extensionTools: ["hello"],
		promptMode: "append",
		prompt: "Review for risks.",
	})
	flow.setActivePreset(id)
	await flow.newSession()
	assert.deepEqual(configs[0].tools, ["read_file", "grep"])
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
