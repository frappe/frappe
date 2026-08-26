import assert from "node:assert/strict"
import test from "node:test"

import { createFlowStore } from "../src/store.js"

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
