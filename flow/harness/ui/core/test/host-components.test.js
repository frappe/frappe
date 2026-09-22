import assert from "node:assert/strict"
import test from "node:test"

import { JSDOM } from "jsdom"

// Vue's DOM runtime captures document at import time.
const dom = new JSDOM("<body></body>", { url: "http://localhost" })
for (const name of ["window", "document", "Document", "Element", "SVGElement", "HTMLElement", "Node"]) {
	globalThis[name] = dom.window[name]
}
dom.window.HTMLElement.prototype.scrollIntoView = () => {}
globalThis.requestAnimationFrame = (callback) => setTimeout(callback, 0)
const { createApp, h, nextTick, reactive } = await import("vue")
const { loadComponent } = await import("./helpers/components.js")
const { applyEvent, initialConversation } = await import("../src/transcript.js")
const Composer = await loadComponent("Composer")
const ApprovalCard = await loadComponent("ApprovalCard")
const ToolGroup = await loadComponent("ToolGroup")
const MessageList = await loadComponent("MessageList")
const ModelButton = await loadComponent("ModelButton")
const SettingsDialog = await loadComponent("SettingsDialog")
const SettingsPage = await loadComponent("SettingsPage")
const SubagentView = await loadComponent("SubagentView")
const TranscriptDialog = await loadComponent("TranscriptDialog")
const WorkspacePanel = await loadComponent("WorkspacePanel")

function mount(t, component, props, flow) {
	const el = document.createElement("div")
	document.body.append(el)
	const app = createApp(component, props)
	app.provide("flow", flow)
	const vm = app.mount(el)
	t.after(() => {
		app.unmount()
		el.remove()
	})
	return { el, vm }
}

for (const disabled of [false, true]) {
	test(`composer skills ${disabled ? "can be disabled" : "stay enabled by default"}`, async (t) => {
		let loads = 0
		const flow = {
			options: { requireCwd: false, maxAttachments: 10, ...(disabled ? { skillsEnabled: false } : {}) },
			state: reactive({
				prefs: { mode: "ask" }, sessionId: null, session: null, models: [], codeRefs: [], queued: [],
				skills: [{ name: "review", description: "Review files" }], conversation: {}, draft: null,
			}),
			loadSkills() { loads++ },
		}
		const { vm, el } = mount(t, Composer, { commands: [], mentions: false }, flow)
		vm.prefill("/")
		await nextTick()
		assert.equal(el.textContent.includes("/skill:review"), !disabled)
		assert.equal(loads, disabled ? 0 : 1)
		vm.prefill("/skill:review investigate")
		await nextTick()
		assert.equal(el.querySelector("textarea").classList.contains("text-transparent"), !disabled)
	})
}

const ArgsView = {
	props: ["arguments"],
	setup: (props) => () => h("dl", { "data-test": "args" }, [
		h("dt", "Status"), h("dd", props.arguments.fields.status),
	]),
}
const args = { fields: { status: "Paid" } }

test("host argument components work in tool groups before and after results", async (t) => {
	const step = reactive({ call: { id: "c1", name: "update_document", arguments: args } })
	const flow = { options: { presentTool: () => ({ argsComponent: ArgsView }) }, state: {} }
	const { el } = mount(t, ToolGroup, { steps: [step] }, flow)
	el.querySelector("button").click()
	await nextTick()
	assert.equal(el.querySelector("[data-test=args] dd").textContent, "Paid")
	assert.equal(el.querySelector("pre"), null)
	step.result = { content: "Document updated" }
	await nextTick()
	assert.equal(el.querySelector("[data-test=args] dd").textContent, "Paid")
	assert.equal(el.querySelector("pre").textContent, "Document updated")
})

test("host argument components preserve approval titles and actions", async (t) => {
	const answers = []
	const flow = {
		options: { presentTool: () => ({ title: "Update invoice?", body: "fallback", argsComponent: ArgsView }) },
		answerApproval: (...answer) => answers.push(answer),
	}
	const { el } = mount(t, ApprovalCard, { call: { id: "c1", name: "update_document", args } }, flow)
	assert.ok(el.textContent.includes("Update invoice?"))
	assert.equal(el.querySelector("[data-test=args] dd").textContent, "Paid")
	assert.equal(el.querySelector("pre"), null)
	for (const label of ["Approve", "Deny"]) {
		[...el.querySelectorAll("button")].find((button) => button.textContent === label).click()
	}
	assert.deepEqual(answers, [["c1", "Approve"], ["c1", "Deny"]])
})

test("the ask-for-changes field takes focus when it opens", async (t) => {
	const flow = { options: {}, answerApproval() {} }
	const { el } = mount(t, ApprovalCard, { call: { id: "c1", name: "bash", args: { command: "pwd" } } }, flow)
	;[...el.querySelectorAll("button")].find((b) => b.textContent === "Ask for changes").click()
	await nextTick()
	await nextTick()
	assert.equal(document.activeElement, el.querySelector("textarea"))
})

test("standalone approvals keep command text and edit diffs", (t) => {
	const calls = [
		{ id: "bash", name: "bash", args: { command: "pwd" } },
		{ id: "edit", name: "edit", args: { path: "a.txt", edits: [{ old: "before", new: "after" }] } },
	]
	const { el } = mount(t, { render: () => calls.map((call) => h(ApprovalCard, { call })) }, {}, { options: {} })
	assert.ok(el.textContent.includes("Run this command?"))
	assert.ok(el.textContent.includes("Apply 1 edit to a.txt?"))
	assert.ok(!el.textContent.includes(" of "), "a lone card carries no batch counter")
	assert.deepEqual([...el.querySelectorAll("pre")].map((pre) => pre.textContent), ["pwd", "- before+ after"])
})

test("standalone tool groups keep display segments and result output", async (t) => {
	const step = { call: { id: "bash", name: "bash", arguments: { command: "pwd" },
		display: [{ text: "Running " }, { text: "pwd", arg: "command" }],
	}, result: { content: "/project" } }
	const { el } = mount(t, ToolGroup, { steps: [step] }, { state: {} })
	assert.ok(el.textContent.includes("Running pwd"))
	assert.equal(el.querySelector("pre"), null)
	el.querySelector("button").click()
	await nextTick()
	assert.equal(el.querySelector("pre").textContent, "/project")
	assert.equal(el.querySelector("[data-test=args]"), null)
})

const ResultView = {
	props: ["arguments", "result"],
	setup: (props) => () => h("table", { "data-test": "result" }, [
		h("tr", [h("td", props.arguments.fields.status), h("td", props.result.content)]),
	]),
}

test("a host renders its own result and stat in place of the text dump", async (t) => {
	const step = reactive({ call: { id: "c1", name: "update_document", arguments: args } })
	const presentTool = (name, callArgs, result) => ({
		argsComponent: ArgsView,
		resultComponent: ResultView,
		stat: result ? "3 updated" : "",
	})
	const { el } = mount(t, ToolGroup, { steps: [step] }, { options: { presentTool }, state: {} })
	el.querySelector("button").click()
	await nextTick()
	assert.equal(el.querySelector("[data-test=args] dd").textContent, "Paid")
	step.result = { content: "3 records" }
	await nextTick()
	assert.equal(el.querySelector("[data-test=result] td").textContent, "Paid")
	assert.equal(el.querySelector("[data-test=args]"), null)
	assert.equal(el.querySelector("pre"), null)
	assert.ok(el.textContent.includes("3 updated"))
})

test("a host's stat beats the derived one, but not the user's decision", async (t) => {
	const presentTool = () => ({ stat: "3 updated" })
	const step = { call: { id: "c1", name: "update_document", arguments: args }, result: { content: "ok", details: { lines: 12 } } }
	const { el } = mount(t, ToolGroup, { steps: [step] }, { options: { presentTool }, state: {} })
	await nextTick()
	assert.ok(el.textContent.includes("3 updated"))
	assert.ok(!el.textContent.includes("12 lines"))

	const denied = { call: { id: "c2", name: "update_document", arguments: args }, result: { content: '{"status": "denied"}' } }
	const card = mount(t, ToolGroup, { steps: [denied] }, { options: { presentTool }, state: {} })
	await nextTick()
	assert.ok(card.el.textContent.includes("denied"))
	assert.ok(!card.el.textContent.includes("3 updated"))
})

test("a host's result view steps aside for an error, which always expands", async (t) => {
	const step = { call: { id: "c1", name: "describe", arguments: args }, result: { content: "boom", is_error: true } }
	const presentTool = () => ({ resultComponent: ResultView, expandable: false })
	const { el } = mount(t, ToolGroup, { steps: [step] }, { options: { presentTool }, state: {} })
	el.querySelector("button").click()
	await nextTick()
	assert.equal(el.querySelector("pre").textContent, "boom")
	assert.equal(el.querySelector("[data-test=result]"), null)
})

test("a host drops the dropdown for its own lookups, name clash or not", async (t) => {
	for (const [name, presented, expanded] of [
		["read", { resultComponent: ResultView }, true],
		["read", {}, false],
		["find_doctypes", { expandable: false }, false],
	]) {
		const step = { call: { id: "c1", name, arguments: args }, result: { content: "[]" } }
		const { el } = mount(t, ToolGroup, { steps: [step] }, { options: { presentTool: () => presented }, state: {} })
		assert.equal(!!el.querySelector("button"), expanded, `${name} ${JSON.stringify(presented)}`)
	}
})

test("a host's turn actions render after each finished turn", async (t) => {
	const TurnActions = {
		props: ["turnKey", "text", "ts"],
		setup: (props) => () => h("span", { "data-test": "actions" }, `${props.turnKey}:${props.text}`),
	}
	const conversation = reactive({
		entries: [
			{ type: "user_message", seq: 2, content: "hi", ts: 10 },
			{ type: "assistant_message", seq: 3, content: [{ type: "text", text: "hello" }], ts: 11 },
		],
		partial: [], running: false, pendingApproval: null, liveLabel: null, liveErrorSeqs: [],
	})
	const flow = {
		options: { turnActions: TurnActions },
		state: reactive({ sessionId: "s1", loading: false, conversation }),
	}
	const { el } = mount(t, MessageList, {}, flow)
	await nextTick()
	assert.equal(el.querySelector("[data-test=actions]")?.textContent, "turn:2:hello")
	flow.options.turnActions = null
	const bare = mount(t, MessageList, {}, { options: {}, state: flow.state })
	await nextTick()
	assert.equal(bare.el.querySelector("[data-test=actions]"), null)
})

test("the composer toolbar defaults to the model button and takes a host's pickers", async (t) => {
	const flow = {
		options: { requireCwd: false, maxAttachments: 10, skillsEnabled: false },
		state: reactive({
			prefs: { mode: "ask" }, sessionId: null, session: null, models: [], codeRefs: [], queued: [],
			skills: [], conversation: {}, draft: null,
		}),
	}
	const bare = mount(t, Composer, { commands: [], mentions: false }, flow)
	assert.ok(bare.el.querySelector("button[title^='Choose Model']"))

	const host = mount(t, {
		render: () => h(Composer, { commands: [], mentions: false }, {
			toolbar: ({ openPalette }) => [
				h("button", { "data-test": "agent", onClick: () => openPalette("thinking") }, "Agent"),
				h(ModelButton, { onOpen: openPalette }),
			],
		}),
	}, {}, flow)
	const agent = host.el.querySelector("[data-test=agent]")
	const model = host.el.querySelector("button[title^='Choose Model']")
	assert.ok(agent.compareDocumentPosition(model) & Node.DOCUMENT_POSITION_FOLLOWING)
	assert.equal(host.el.querySelector("[data-stub=ThinkingPalette]"), null)
	agent.click()
	await nextTick()
	assert.ok(host.el.querySelector("[data-stub=ThinkingPalette]"))

	model.click()
	await nextTick()
	const entries = [...host.el.querySelectorAll("[role=menuitem]")].map((entry) => entry.textContent.trim())
	assert.deepEqual(entries, ["ModelChoose Model", "ThinkingDefault"])
	host.el.querySelector("[role=menuitem]").click()
	await nextTick()
	assert.equal(host.el.querySelector("[role=menuitem]"), null)
	assert.ok(host.el.querySelector("[data-stub=ModelPalette]"))
})

test("the composer shows a pending batch one call at a time, above the box", async (t) => {
	const pending = {
		seq: 4,
		calls: [
			{ id: "c1", name: "bash", args: { command: "pwd" } },
			{ id: "c2", name: "write", args: { path: "a.txt", content: "hi" } },
		],
		answers: {},
	}
	const flow = {
		options: { requireCwd: false, maxAttachments: 10, skillsEnabled: false },
		state: reactive({
			prefs: { mode: "ask" }, sessionId: "s1", session: null, models: [], codeRefs: [], queued: [],
			skills: [], conversation: { pendingApproval: pending }, draft: null,
		}),
		answerApproval: (id, answer) => (flow.state.conversation.pendingApproval.answers[id] = answer),
	}
	const { el } = mount(t, Composer, { commands: [], mentions: false }, flow)
	const approve = () => [...el.querySelectorAll("button")].find((button) => button.textContent === "Approve")
	assert.ok(el.textContent.includes("Run this command?"))
	assert.ok(!el.textContent.includes("Write a.txt?"))
	assert.ok(el.textContent.includes("1 of 2"))
	assert.ok(approve().compareDocumentPosition(el.querySelector("fieldset")) & Node.DOCUMENT_POSITION_FOLLOWING)

	approve().click()
	await nextTick()
	assert.ok(!el.textContent.includes("Run this command?"))
	assert.ok(el.textContent.includes("Write a.txt?"))
	assert.ok(el.textContent.includes("2 of 2"))

	approve().click()
	await nextTick()
	assert.equal(approve(), undefined)
	assert.ok(!el.textContent.includes("Write a.txt?"))
})

test("the composer takes a host's placeholder and approval-mode copy", async (t) => {
	const flow = {
		options: { requireCwd: false, maxAttachments: 10, skillsEnabled: false },
		state: reactive({
			prefs: { mode: "ask" }, sessionId: null, session: null, models: [], codeRefs: [], queued: [],
			skills: [], conversation: {}, draft: null,
		}),
	}
	const modes = [
		{ id: "ask", label: "Ask first", desc: "Pauses before documents change." },
		{ id: "auto", label: "Just do it", desc: "Never asks." },
	]
	const { el } = mount(t, Composer, { commands: [], mentions: false, placeholder: "Ask Sales…", modes }, flow)
	assert.equal(el.querySelector("textarea").placeholder, "Ask Sales…")
	const button = el.querySelector("button[title='Approval mode']")
	assert.equal(button.textContent.trim(), "Ask first")
	button.click()
	await nextTick()
	const menu = el.querySelector("[role=menu]").textContent
	for (const text of ["Ask first", "Pauses before documents change.", "Just do it", "Never asks."]) assert.ok(menu.includes(text), text)
})

test("a sent message is a bubble before the server echoes it", async (t) => {
	const conversation = reactive({
		...initialConversation(),
		sending: [{ key: "sending:1", entry: { type: "user_message", content: [{ type: "text", text: "count the todos" }], ts: 10 } }],
	})
	const flow = { options: {}, state: reactive({ sessionId: "s1", loading: false, conversation }) }
	const { el } = mount(t, MessageList, {}, flow)
	await nextTick()
	assert.ok(el.textContent.includes("count the todos"))
	assert.ok(el.textContent.includes("Working"))

	// the server's copy arrives: the same message, now a real entry
	applyEvent(conversation, { type: "user_message", seq: 1, content: [{ type: "text", text: "count the todos" }], ts: 11 })
	await nextTick()
	assert.equal(conversation.sending.length, 0)
	assert.equal(el.textContent.match(/count the todos/g).length, 1)
})

test("the composer empties at once and spins the send button until sending succeeds", async (t) => {
	let finishSend
	let sent
	const flow = {
		options: { requireCwd: false, maxAttachments: 10, skillsEnabled: false },
		state: reactive({
			prefs: { mode: "ask" }, sessionId: "s1", session: null, models: [], codeRefs: [], queued: [],
			skills: [], conversation: { running: false }, draft: null,
		}),
		send(message, attachments) {
			sent = { message, attachments }
			return new Promise((resolve) => (finishSend = resolve))
		},
		clearCodeRefs() { this.state.codeRefs = [] },
		notify() {},
	}
	const { el, vm } = mount(t, Composer, { commands: [], mentions: false, imagesOnly: false }, flow)
	vm.prefill("Review this")
	const input = el.querySelector("input[type=file]")
	Object.defineProperty(input, "files", {
		configurable: true,
		value: [new dom.window.File(["document"], "notes.pdf", { type: "application/pdf" })],
	})
	input.dispatchEvent(new dom.window.Event("change", { bubbles: true }))
	await nextTick()
	assert.ok(el.textContent.includes("notes.pdf"))

	el.querySelector("button[title='Send']").click()
	await nextTick()

	// the message is already a bubble in the thread; its attachment stays staged here
	assert.equal(el.querySelector("textarea").value, "")
	assert.ok(el.textContent.includes("notes.pdf"))
	assert.equal(el.querySelector('[role="status"]'), null)
	const sendButton = el.querySelector("button[title='Send']")
	assert.equal(sendButton.disabled, true)
	assert.equal(sendButton.getAttribute("aria-busy"), "true")
	assert.ok(sendButton.querySelector(".animate-spin"))
	assert.equal(sent.message, "Review this")
	assert.equal(sent.attachments[0].name, "notes.pdf")
	flow.state.conversation.running = true
	await nextTick()
	assert.ok(el.querySelector("button[title='Send'] .animate-spin"))
	finishSend(true)
	await new Promise((resolve) => setImmediate(resolve))
	assert.equal(el.querySelector("textarea").value, "")
	assert.ok(!el.textContent.includes("notes.pdf"))
	assert.equal(el.querySelector(".animate-spin"), null)
	assert.ok(el.querySelector("button[title='Stop']"))
})

test("the composer retains an attachment draft when sending fails", async (t) => {
	const flow = {
		options: { requireCwd: false, maxAttachments: 10, skillsEnabled: false },
		state: reactive({
			prefs: { mode: "ask" }, sessionId: "s1", session: null, models: [], codeRefs: [], queued: [],
			skills: [], conversation: { running: false }, draft: null,
		}),
		async send() { return false },
		clearCodeRefs() { this.state.codeRefs = [] },
		notify() {},
	}
	const { el, vm } = mount(t, Composer, { commands: [], mentions: false, imagesOnly: false }, flow)
	vm.prefill("Review this")
	const input = el.querySelector("input[type=file]")
	Object.defineProperty(input, "files", {
		configurable: true,
		value: [new dom.window.File(["document"], "notes.pdf", { type: "application/pdf" })],
	})
	input.dispatchEvent(new dom.window.Event("change", { bubbles: true }))
	await nextTick()
	el.querySelector("button[title='Send']").click()
	await new Promise((resolve) => setImmediate(resolve))

	assert.equal(el.querySelector("textarea").value, "Review this")
	assert.ok(el.textContent.includes("notes.pdf"))
	assert.equal(el.querySelector("button[title='Send']").disabled, false)
	assert.equal(el.querySelector(".animate-spin"), null)
})

function preparingComposer(t) {
	const requests = []
	const sent = []
	const discarded = []
	const flow = {
		options: { requireCwd: false, maxAttachments: 10, skillsEnabled: false },
		state: reactive({
			prefs: { mode: "ask" }, sessionId: null, session: null, models: [], codeRefs: [], queued: [],
			skills: [], conversation: { running: false }, draft: null,
		}),
		prepareAttachment(file) {
			return new Promise((resolve, reject) => requests.push({ file, resolve, reject }))
		},
		async discardAttachments(ids) { discarded.push(...ids) },
		async send(text, items) { sent.push({ text, ids: items.map((item) => item.id) }); return true },
		clearCodeRefs() { this.state.codeRefs = [] },
		notify() {},
	}
	const { el, vm } = mount(t, Composer, { commands: [], mentions: false, imagesOnly: false }, flow)
	vm.prefill("Read this")
	const input = el.querySelector("input[type=file]")
	Object.defineProperty(input, "files", {
		value: [new dom.window.File(["document"], "notes.pdf", { type: "application/pdf" })],
	})
	input.dispatchEvent(new dom.window.Event("change", { bubbles: true }))
	return { el, flow, requests, sent, discarded }
}

test("attaching starts preparation before a session exists, and send waits for it", async (t) => {
	const { el, flow, requests, sent, discarded } = preparingComposer(t)
	await nextTick()
	assert.equal(requests.length, 1)
	assert.equal(flow.state.sessionId, null)
	assert.equal(el.querySelector('[role="status"]').getAttribute("aria-label"), "Preparing notes.pdf")
	el.querySelector("button[title='Send']").click()
	await nextTick()
	assert.equal(sent.length, 0)
	assert.equal(el.querySelector("textarea").value, "Read this")
	assert.ok(el.querySelector("button[title='Send'] .animate-spin"))
	requests[0].resolve({ id: "F1", name: "notes.pdf", kind: "file" })
	await new Promise((resolve) => setImmediate(resolve))
	assert.deepEqual(sent, [{ text: "Read this", ids: ["F1"] }])
	assert.equal(requests.length, 1)
	assert.equal(el.querySelector("textarea").value, "")
	assert.deepEqual(discarded, [])
})

test("removing an attachment during preparation discards it when upload completes", async (t) => {
	const { el, requests, discarded, sent } = preparingComposer(t)
	await nextTick()
	el.querySelector("button[aria-label='Remove notes.pdf']").click()
	requests[0].resolve({ id: "F1", name: "notes.pdf", kind: "file" })
	await new Promise((resolve) => setImmediate(resolve))
	assert.deepEqual(discarded, ["F1"])
	assert.equal(sent.length, 0)
	assert.ok(!el.textContent.includes("notes.pdf"))
})

test("failed preparation keeps the draft and can be retried before sending", async (t) => {
	const { el, requests, sent } = preparingComposer(t)
	await nextTick()
	requests[0].reject(new Error("Upload failed"))
	await new Promise((resolve) => setImmediate(resolve))
	assert.ok(el.textContent.includes("Upload failed"))
	el.querySelector("button[title='Send']").click()
	await nextTick()
	assert.equal(sent.length, 0)
	assert.equal(el.querySelector("textarea").value, "Read this")
	el.querySelector("button[aria-label='Retry notes.pdf']").click()
	await nextTick()
	requests[1].resolve({ id: "F2", name: "notes.pdf", kind: "file" })
	await new Promise((resolve) => setImmediate(resolve))
	assert.equal(el.querySelector('[role="status"]'), null)
	el.querySelector("button[title='Send']").click()
	await new Promise((resolve) => setImmediate(resolve))
	assert.deepEqual(sent, [{ text: "Read this", ids: ["F2"] }])
})

test("switching sessions discards a prepared unsent file", async (t) => {
	const { flow, requests, discarded } = preparingComposer(t)
	await nextTick()
	requests[0].resolve({ id: "F1", name: "notes.pdf", kind: "file" })
	await new Promise((resolve) => setImmediate(resolve))
	flow.state.sessionId = "other"
	await nextTick()
	assert.deepEqual(discarded, ["F1"])
})

test("switching sessions while send waits for preparation does not send to the new session", async (t) => {
	const { el, flow, requests, sent } = preparingComposer(t)
	await nextTick()
	el.querySelector("button[title='Send']").click()
	flow.state.sessionId = "other"
	await nextTick()
	requests[0].resolve({ id: "F1", name: "notes.pdf", kind: "file" })
	await new Promise((resolve) => setImmediate(resolve))
	assert.equal(sent.length, 0)
	assert.equal(el.querySelector("textarea").value, "Read this")
})

test("the message list's empty state is a slot", (t) => {
	const conversation = { entries: [], partial: [], running: false, pendingApproval: null, liveLabel: null, liveErrorSeqs: [] }
	const flow = { options: {}, state: reactive({ sessionId: null, loading: false, conversation }) }
	const bare = mount(t, MessageList, {}, flow)
	assert.ok(bare.el.textContent.includes("What would you like to build?"))
	const host = mount(t, {
		render: () => h(MessageList, null, { empty: () => h("h2", { "data-test": "empty" }, "How can I help?") }),
	}, {}, flow)
	assert.equal(host.el.querySelector("[data-test=empty]").textContent, "How can I help?")
	assert.ok(!host.el.textContent.includes("What would you like to build?"))
})

test("an existing session without saved messages shows the empty state after reload", (t) => {
	const flow = {
		options: {},
		state: reactive({ sessionId: "empty-session", loading: false, conversation: {
			entries: [], partial: [], running: false, pendingApproval: null, liveLabel: null, liveErrorSeqs: [],
		} }),
	}
	const { el } = mount(t, MessageList, {}, flow)
	assert.ok(el.textContent.includes("What would you like to build?"))
})

test("the settings shell renders a host's tabs and panels", (t) => {
	const groups = [{ label: "Settings", tabs: [{ id: "alpha", label: "Alpha", icon: "x" }, { id: "beta", label: "Beta", icon: "y" }] }]
	const flow = { state: reactive({ settingsOpen: true }), setSettingsOpen() {} }
	const { el } = mount(t, {
		render: () => h(SettingsDialog, { groups }, {
			alpha: () => h("p", { "data-test": "alpha" }, "A"),
			beta: () => h("p", { "data-test": "beta" }, "B"),
		}),
	}, {}, flow)
	assert.deepEqual([...el.querySelectorAll("[data-stub=SettingsNavItem]")].map((b) => b.textContent.trim()), ["Alpha", "Beta"])
	assert.deepEqual([...el.querySelectorAll("[data-stub=SettingsPanel]")].map((p) => `${p.dataset.value}:${p.textContent.trim()}`), ["alpha:A", "beta:B"])
})

test("a host's own command opens its palette slot", async (t) => {
	const flow = {
		options: { requireCwd: false, maxAttachments: 10, skillsEnabled: false },
		state: reactive({
			prefs: { mode: "ask" }, sessionId: null, session: null, models: [], codeRefs: [], queued: [],
			skills: [], conversation: {}, draft: null,
		}),
	}
	const commands = [{ name: "agents", label: "Agent", icon: "user", hint: "choose the agent", view: "agents" }, "model"]
	const { el, vm } = mount(t, {
		render: () => h(Composer, { ref: "composer", commands, mentions: false }, {
			palette: ({ view, close }) => (view === "agents" ? h("div", { "data-test": "host-palette", onClick: close }, view) : null),
		}),
	}, {}, flow)
	vm.$refs.composer.prefill("/")
	await nextTick()
	assert.deepEqual([...el.querySelectorAll("[data-palette-item] code")].map((c) => c.textContent), ["/agents", "/model"])
	el.querySelector("[data-palette-item]").click()
	await nextTick()
	assert.equal(el.querySelector("[data-test=host-palette]").textContent, "agents")
	el.querySelector("[data-test=host-palette]").click()
	await nextTick()
	assert.equal(el.querySelector("[data-test=host-palette]"), null)
})

test("a disabled composer is shown but inert, its host pickers included", async (t) => {
	const flow = {
		options: { requireCwd: false, maxAttachments: 10, skillsEnabled: false },
		state: reactive({
			prefs: { mode: "ask" }, sessionId: null, session: null, models: [], codeRefs: [], queued: [],
			skills: [], conversation: {}, draft: null,
		}),
	}
	const { el } = mount(t, {
		render: () => h(Composer, { commands: [], mentions: false, disabled: true }, {
			toolbar: () => h("button", { "data-test": "agent" }, "Agent"),
		}),
	}, {}, flow)
	assert.ok(el.querySelector("textarea").matches(":disabled"))
	assert.ok(el.querySelector("button[title='Send']").matches(":disabled"))
	assert.ok(el.querySelector("[data-test=agent]").matches(":disabled"))
})

test("a settings page takes a way back and actions beside its heading", (t) => {
	let backs = 0
	const { el } = mount(t, {
		render: () => h(SettingsPage, { title: "Edit agent", back: "Back to agents", onBack: () => backs++ }, {
			actions: () => h("button", { "data-test": "toggle" }, "Enabled"),
			default: () => h("p", "fields"),
			footer: () => h("button", { "data-test": "save" }, "Save"),
		}),
	}, {}, {})
	assert.equal(el.querySelector("h2").textContent, "Edit agent")
	assert.ok(el.querySelector("[data-test=toggle]"))
	assert.ok(el.querySelector(".border-t [data-test=save]"), "the footer sits outside the scrolling body")
	el.querySelector("button[title='Back to agents']").click()
	assert.equal(backs, 1)
	const bare = mount(t, SettingsPage, { title: "General" }, {})
	assert.equal(bare.el.querySelector(".flow-icon-btn"), null)
	assert.equal(bare.el.querySelector(".border-t"), null)
})


test("rewind controls follow the host client's capability", async (t) => {
	const { createFlowStore } = await import("../src/store.js")
	const UserBubble = await loadComponent("UserBubble")
	for (const supported of [false, true]) {
		const client = supported ? { rewind() {} } : {}
		const store = createFlowStore(client, { requireCwd: false, skillsEnabled: false })
		const { el } = mount(t, UserBubble, { entry: { type: "user_message", seq: 2, content: "hello" } }, store)
		assert.equal(!!el.querySelector('button[title="Rewind to this message"]'), supported)
		const composer = mount(t, Composer, { mentions: false }, store)
		composer.vm.prefill("/rewind")
		await nextTick()
		assert.equal(composer.el.textContent.includes("branch from before your last message"), supported)
	}
})

test("a skill the user started keeps its blue command prefix in the bubble", async (t) => {
	const { createFlowStore } = await import("../src/store.js")
	const UserBubble = await loadComponent("UserBubble")
	const store = createFlowStore({}, { requireCwd: false, skillsEnabled: false })
	const content =
		'<skill name="security-review" location="/skills/security-review/SKILL.md">\nbody\n</skill>\n\ncheck this branch'
	const { el } = mount(t, UserBubble, { entry: { type: "user_message", seq: 2, content } }, store)
	assert.equal(el.querySelector(".text-ink-blue-6").textContent, "/skill:security-review")
	assert.ok(el.textContent.includes("/skill:security-review check this branch"))
	assert.ok(!el.textContent.includes("body"))
})

function rowButton(el, text) {
	return [...el.querySelectorAll("button")].find((button) => button.textContent.includes(text))
}

test("a tool row left open stays open and unfolded when the run ends", async (t) => {
	const conversation = reactive(initialConversation())
	applyEvent(conversation, { type: "run_started", seq: 1, ts: 10 })
	applyEvent(conversation, { type: "user_message", seq: 2, ts: 10, content: "list files" })
	applyEvent(conversation, {
		type: "assistant_message",
		seq: 3,
		ts: 11,
		content: [{ type: "tool_call", id: "call-1", name: "bash", arguments: { command: "ls" } }],
		stop_reason: "tool_use",
	})
	applyEvent(conversation, { type: "tool_result", seq: 4, ts: 12, tool_call_id: "call-1", content: "a.js" })
	const flow = { options: {}, state: reactive({ sessionId: "s1", loading: false, conversation }) }
	const { el } = mount(t, MessageList, {}, flow)
	await nextTick()
	rowButton(el, "ls").click()
	await nextTick()
	assert.ok(el.querySelector("pre"))

	applyEvent(conversation, { type: "assistant_message", seq: 5, ts: 13, content: [{ type: "text", text: "One file." }], stop_reason: "stop" })
	applyEvent(conversation, { type: "run_ended", seq: 6, ts: 13, reason: "done" })
	await nextTick()
	const fold = el.querySelector("[data-turn-fold] button")
	assert.equal(fold.getAttribute("aria-expanded"), "true")
	assert.ok(el.querySelector("pre"))

	// folding it by hand closes the row with it
	fold.click()
	await nextTick()
	assert.equal(fold.getAttribute("aria-expanded"), "false")
	assert.equal(el.querySelector("pre"), null)
})

test("an opened thought stays open as it merges into a tool group and the run ends", async (t) => {
	const conversation = reactive(initialConversation())
	applyEvent(conversation, { type: "run_started", seq: 1, ts: 10 })
	applyEvent(conversation, { type: "user_message", seq: 2, ts: 10, content: "list files" })
	applyEvent(conversation, { type: "thinking_delta", thinking: "I should list them" })
	const flow = { options: {}, state: reactive({ sessionId: "s1", loading: false, conversation }) }
	const { el } = mount(t, MessageList, {}, flow)
	await nextTick()
	const panel = () => el.querySelector("[data-stub=MarkdownContent]")
	assert.equal(panel(), null)
	rowButton(el, "Thinking").click()
	await nextTick()
	assert.ok(panel())

	applyEvent(conversation, { type: "tool_call_display_ready", id: "call-1", name: "bash", arguments: { command: "ls" } })
	await nextTick()
	assert.ok(rowButton(el, "Thought"))
	assert.ok(panel())

	applyEvent(conversation, {
		type: "assistant_message",
		seq: 3,
		ts: 11,
		content: [
			{ type: "thinking", thinking: "I should list them" },
			{ type: "tool_call", id: "call-1", name: "bash", arguments: { command: "ls" } },
		],
		stop_reason: "tool_use",
	})
	applyEvent(conversation, { type: "tool_result", seq: 4, ts: 12, tool_call_id: "call-1", content: "a.js" })
	applyEvent(conversation, { type: "assistant_message", seq: 5, ts: 13, content: [{ type: "text", text: "One file." }], stop_reason: "stop" })
	applyEvent(conversation, { type: "run_ended", seq: 6, ts: 13, reason: "done" })
	await nextTick()
	assert.equal(el.querySelector("[data-turn-fold] button").getAttribute("aria-expanded"), "true")
	assert.ok(panel())
})

test("the Default preset locks the core tools and takes bundled and extension picks", async (t) => {
	const { createFlowStore } = await import("../src/store.js")
	const SettingsPresets = await loadComponent("SettingsPresets")
	globalThis.localStorage = { getItem: () => null, setItem() {} }
	t.after(() => delete globalThis.localStorage)
	const tools = [
		{ name: "bash", description: "Run a command", extension: null, bundled: false },
		{ name: "grep", description: "Search files", extension: null, bundled: true },
		{ name: "hello", description: "Say hi", extension: "hello", bundled: false },
	]
	const store = createFlowStore({ async tools() { return { tools } } }, { requireCwd: false, skillsEnabled: false })
	const { el } = mount(t, SettingsPresets, {}, store)
	assert.match(el.textContent, /Core tools and the built-in prompt/) // no list yet: nothing to count
	await store.refreshTools()
	await nextTick()
	assert.match(el.textContent, /2 of 3 tools/) // the Default row: core and extensions on, bundled off

	el.querySelector("button[title='Edit preset']").click() // the Default row comes first
	await nextTick()
	assert.equal(el.querySelector("h2").textContent, "Default preset")
	assert.equal(el.querySelector("input[type=text]"), null, "no name to edit")
	assert.equal(el.querySelector("textarea"), null, "no prompt to edit")
	const boxes = [...el.querySelectorAll("input[type=checkbox]")]
	assert.deepEqual(boxes.map((box) => [box.checked, box.disabled]), [[true, true], [false, false], [true, false]])
	const save = () => [...el.querySelectorAll("button")].find((b) => b.textContent === "Save")
	assert.ok(save().disabled)

	boxes[1].click()
	await nextTick()
	assert.ok(!save().disabled)
	save().click()
	await nextTick()
	assert.deepEqual(store.state.prefs.defaultPreset, { tools: ["grep"], extensionTools: ["hello"] })
	assert.match(el.textContent, /3 of 3 tools/)
})

function subagentConversation() {
	const conversation = reactive(initialConversation())
	applyEvent(conversation, { type: "run_started", seq: 1, ts: 10 })
	applyEvent(conversation, { type: "user_message", seq: 2, ts: 10, content: "go" })
	applyEvent(conversation, {
		type: "assistant_message",
		seq: 3,
		ts: 11,
		content: [{ type: "tool_call", id: "c1", name: "subagent", arguments: { task: "count", description: "count beans" } }],
	})
	applyEvent(conversation, { type: "run_started", seq: 4, ts: 11, subagent_id: "c1" })
	applyEvent(conversation, { type: "user_message", seq: 5, ts: 11, content: "count", subagent_id: "c1" })
	return conversation
}

test("a sub-agent's row opens its tab and shows its state instead of a dropdown", async (t) => {
	const conversation = subagentConversation()
	const opened = []
	const flow = { options: {}, state: reactive({ sessionId: "s1", loading: false, conversation }), openSubagent: (id) => opened.push(id) }
	const { el } = mount(t, MessageList, {}, flow)
	await nextTick()
	const row = () => rowButton(el, "count beans")
	assert.ok(row().textContent.includes("Working"))
	applyEvent(conversation, { type: "thinking_delta", thinking: "hmm", subagent_id: "c1" })
	await nextTick()
	assert.ok(row().textContent.includes("Thinking"))
	row().click()
	await nextTick()
	assert.deepEqual(opened, ["c1"])
	assert.equal(el.querySelector("pre"), null)

	applyEvent(conversation, { type: "assistant_message", seq: 6, ts: 12, content: [{ type: "text", text: "forty-two" }], subagent_id: "c1" })
	applyEvent(conversation, { type: "run_ended", seq: 7, ts: 12, reason: "done", subagent_id: "c1" })
	applyEvent(conversation, {
		type: "tool_result", seq: 8, ts: 12, tool_call_id: "c1", name: "subagent",
		content: "forty-two\n\n[subagent_id: c1]", details: { subagent_id: "c1", agent: "researcher", end_reason: "done" },
	})
	await nextTick()
	assert.ok(row().textContent.includes("researcher"))
	assert.ok(!el.textContent.includes("forty-two")) // the child's answer lives in its tab
})

test("a host without a workspace panel keeps the sub-agent row's dropdown", async (t) => {
	const conversation = subagentConversation()
	applyEvent(conversation, { type: "assistant_message", seq: 6, ts: 12, content: [{ type: "text", text: "forty-two" }], subagent_id: "c1" })
	applyEvent(conversation, { type: "run_ended", seq: 7, ts: 12, reason: "done", subagent_id: "c1" })
	applyEvent(conversation, {
		type: "tool_result", seq: 8, ts: 12, tool_call_id: "c1", name: "subagent",
		content: "forty-two\n\n[subagent_id: c1]", details: { subagent_id: "c1", agent: "general", end_reason: "done" },
	})
	const opened = []
	const flow = { options: { workspace: false }, state: reactive({ sessionId: "s1", loading: false, conversation }), openSubagent: (id) => opened.push(id) }
	const { el } = mount(t, MessageList, {}, flow)
	await nextTick()
	rowButton(el, "count beans").click()
	await nextTick()
	assert.deepEqual(opened, [])
	assert.ok(el.querySelector("pre").textContent.includes("forty-two"))
})

test("a sub-agent's tab draws the child's thread with the session's own rows", async (t) => {
	const conversation = subagentConversation()
	const flow = { options: {}, capabilities: { rewind: true }, state: reactive({ sessionId: "s1", loading: false, conversation }) }
	const { el } = mount(t, SubagentView, { id: "c9" }, flow)
	assert.ok(el.textContent.includes("Starting…"))

	const { el: view } = mount(t, SubagentView, { id: "c1" }, flow)
	await nextTick()
	assert.ok(view.textContent.includes("count")) // the task bubble
	assert.equal(view.querySelector("button[title='Rewind to this message']"), null)
	applyEvent(conversation, {
		type: "assistant_message", seq: 6, ts: 12, subagent_id: "c1",
		content: [{ type: "tool_call", id: "c2", name: "bash", arguments: { command: "wc -l beans" } }],
	})
	applyEvent(conversation, { type: "tool_result", seq: 7, ts: 12, tool_call_id: "c2", content: "42", subagent_id: "c1" })
	await nextTick()
	rowButton(view, "wc -l beans").click() // the same tool dropdowns
	await nextTick()
	assert.equal(view.querySelector("pre").textContent, "42")

	applyEvent(conversation, { type: "assistant_message", seq: 8, ts: 13, content: [{ type: "text", text: "forty-two" }], subagent_id: "c1" })
	applyEvent(conversation, { type: "run_ended", seq: 9, ts: 13, reason: "done", subagent_id: "c1" })
	await nextTick()
	assert.ok(view.querySelector("[data-turn-fold] button").textContent.includes("Worked")) // and the same turn fold
	assert.ok(view.querySelector("[data-stub='AssistantText']"))
})

test("the workspace panel draws a sub-agent's tab itself and takes the host's menu, view and empty state", async (t) => {
	const conversation = subagentConversation()
	const workspace = reactive({
		open: true, maximized: false, view: null, active: "c1",
		tabs: [{ kind: "subagent", path: "c1", name: "Sub-agent: beans" }],
	})
	const flow = { options: {}, state: reactive({ sessionId: "s1", loading: false, conversation, workspace, prefs: {} }) }
	const panel = {
		render: () => h(WorkspacePanel, null, {
			actions: () => h("button", { "data-host": "add" }, "+"),
			view: ({ tab }) => h("div", { "data-host": "view" }, tab?.path ?? "no tab"),
			empty: () => h("p", { "data-host": "empty" }, "Nothing open"),
		}),
	}
	const { el } = mount(t, panel, {}, flow)
	await nextTick()
	assert.ok(el.querySelector("[role='tab']").textContent.includes("Sub-agent: beans"))
	assert.ok(el.querySelector("[data-host='add']"))
	assert.ok(el.textContent.includes("count")) // the child's task bubble: the panel draws the thread
	assert.equal(el.querySelector("[data-host='view']"), null)

	workspace.tabs.push({ kind: "editor", path: "beans.txt", name: "beans.txt" })
	workspace.active = "beans.txt"
	await nextTick()
	assert.equal(el.querySelector("[data-host='view']").textContent, "beans.txt")
	assert.ok(!el.textContent.includes("count")) // the thread left with its tab

	workspace.tabs.splice(0)
	workspace.active = null
	workspace.view = "files" // a view with no tab yet stands in for one
	await nextTick()
	assert.equal(el.querySelector("[data-host='view']").textContent, "no tab")
	assert.ok(el.querySelector("[role='tab']").textContent.includes("Files"))

	workspace.view = null
	await nextTick()
	assert.equal(el.querySelector("[role='tab']"), null)
	assert.equal(el.querySelector("[data-host='add']"), null)
	assert.ok(el.querySelector("[data-host='empty']"))
})

test("a sub-agent's question shows in the composer, named after the sub-agent", async (t) => {
	const conversation = subagentConversation()
	const calls = [{ id: "c2", name: "bash", args: { command: "rm x" } }]
	applyEvent(conversation, { type: "approval_required", seq: 6, calls, subagent_id: "c1" })
	applyEvent(conversation, { type: "run_ended", seq: 7, reason: "paused", subagent_id: "c1" })
	const answers = []
	const flow = {
		options: { requireCwd: false, maxAttachments: 10, skillsEnabled: false },
		state: reactive({
			prefs: { mode: "ask" }, sessionId: "s1", session: null, models: [], codeRefs: [], queued: [],
			skills: [], conversation, draft: null,
		}),
		answerApproval: (id, answer) => answers.push([id, answer]),
	}
	const { el } = mount(t, Composer, { commands: [], mentions: false }, flow)
	assert.ok(el.textContent.includes("Run this command?"))
	assert.ok(el.textContent.includes("Sub-agent: count beans"))
	;[...el.querySelectorAll("button")].find((button) => button.textContent === "Approve").click()
	assert.deepEqual(answers, [["c2", "Approve"]])

	// the session's run ending takes the question with it
	applyEvent(conversation, { type: "run_ended", seq: 8, reason: "aborted" })
	await nextTick()
	assert.ok(!el.textContent.includes("Run this command?"))
})

test("the transcript shows request usage beside assistant responses", async (t) => {
	const conversation = initialConversation()
	applyEvent(conversation, { type: "user_message", seq: 2, content: "find the leak" })
	applyEvent(conversation, {
		type: "assistant_message",
		seq: 3,
		content: [{ type: "tool_call", id: "a", name: "read", arguments: { path: "server.py" } }],
	})
	applyEvent(conversation, {
		type: "usage",
		seq: 4,
		input_tokens: 1000,
		output_tokens: 40,
		cache_read_tokens: 900,
		context_window: 200000,
	})
	applyEvent(conversation, { type: "tool_result", seq: 5, tool_call_id: "a", name: "read", content: "leaky line" })

	const flow = {
		state: reactive({ transcriptOpen: true, conversation, session: null }),
		setTranscriptOpen(open) {
			flow.state.transcriptOpen = open
		},
	}
	mount(t, TranscriptDialog, {}, flow)
	await nextTick()

	const panel = document.querySelector("[role=dialog]")
	assert.match(panel.textContent, /Tokens1k.*Input1k.*Output40.*Model calls1.*Context1kof 200k/s)
	assert.match(panel.textContent, /user\s*find the leak/)
	// cached is a share of the input, not a number to add to it
	assert.match(panel.textContent, /assistant\s*in 1k \(90% cached\)\s*out 40/)
	// every tool reads the same way: the call, then what it returned
	assert.match(panel.textContent, /tool\s*read\s*input.*"path": "server\.py".*output\s*leaky line/s)
	assert.doesNotMatch(panel.textContent, /estimated|reported|~4|prompt & tool definitions/)
	assert.equal(panel.querySelectorAll("button").length, 1) // only the close button
	assert.equal(panel.querySelectorAll("[data-stub=Badge]").length, 2)
})

test("the transcript names an attachment-only message and flags a failed call", async (t) => {
	const conversation = initialConversation()
	applyEvent(conversation, {
		type: "user_message",
		seq: 2,
		content: [{ type: "attachment", id: "i1", name: "screen.png", kind: "image" }],
	})
	applyEvent(conversation, {
		type: "assistant_message",
		seq: 3,
		content: [{ type: "tool_call", id: "a", name: "read", arguments: { path: "gone.py" } }],
	})
	applyEvent(conversation, { type: "tool_result", seq: 4, tool_call_id: "a", name: "read", content: "ENOENT", is_error: true })

	const flow = {
		state: reactive({ transcriptOpen: true, conversation, session: null }),
		setTranscriptOpen(open) {
			flow.state.transcriptOpen = open
		},
	}
	mount(t, TranscriptDialog, {}, flow)
	await nextTick()

	const panel = document.querySelector("[role=dialog]")
	assert.match(panel.textContent, /user\s*screen\.png/) // the row is not blank
	assert.deepEqual([...panel.querySelectorAll("[data-stub=Badge]")].map((b) => b.textContent), ["error"])
})
