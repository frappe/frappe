import assert from "node:assert/strict"
import test from "node:test"

import { JSDOM } from "jsdom"

// Vue's DOM runtime captures document at import time.
const dom = new JSDOM("<body></body>", { url: "http://localhost" })
for (const name of ["window", "document", "Document", "Element", "SVGElement", "HTMLElement", "Node"]) {
	globalThis[name] = dom.window[name]
}
dom.window.HTMLElement.prototype.scrollIntoView = () => {}
// jsdom lacks the inert property that browsers reflect onto the attribute
Object.defineProperty(dom.window.HTMLElement.prototype, "inert", {
	get() {
		return this.hasAttribute("inert")
	},
	set(value) {
		this.toggleAttribute("inert", !!value)
	},
})
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
const FilesBar = await loadComponent("FilesBar")
const SessionSidebar = await loadComponent("SessionSidebar")
const ModelPalette = await loadComponent("ModelPalette")
const FileMentionPalette = await loadComponent("FileMentionPalette")
const ProvidersDialog = await loadComponent("ProvidersDialog")
const SettingsSkills = await loadComponent("SettingsSkills")
const ChatHeader = await loadComponent("ChatHeader")
const MarkdownContent = await loadComponent("MarkdownContent")

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

// jsdom measures nothing: a test that needs boxes stubs them for its duration
const box = (left, top, right, bottom) => ({ left, top, right, bottom, width: right - left, height: bottom - top })
function measure(t, boxes) {
	const protos = { element: dom.window.Element.prototype, range: dom.window.Range.prototype }
	const before = { element: protos.element.getBoundingClientRect, range: protos.range.getBoundingClientRect }
	for (const kind of ["element", "range"]) protos[kind].getBoundingClientRect = () => boxes[kind]
	t.after(() => {
		for (const kind of ["element", "range"]) protos[kind].getBoundingClientRect = before[kind]
	})
}

for (const disabled of [false, true]) {
	test(`composer skills ${disabled ? "can be disabled" : "stay enabled by default"}`, async (t) => {
		let loads = 0
		const flow = {
			options: { requireCwd: false, maxAttachments: 10, ...(disabled ? { skillsEnabled: false } : {}) },
			state: reactive({
				prefs: { mode: "ask" }, sessionId: null, session: null, models: [], codeRefs: [], quotes: [], queued: [],
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

test("mid-message, a slash offers skills only and puts the one picked where it was typed", async (t) => {
	const flow = {
		options: { requireCwd: false, maxAttachments: 10 },
		state: reactive({
			prefs: { mode: "ask" }, sessionId: null, session: null, models: [], codeRefs: [], quotes: [], queued: [],
			skills: [{ name: "review", description: "Review files" }], conversation: {}, draft: null,
		}),
		loadSkills() {},
	}
	const { vm, el } = mount(t, Composer, { commands: ["new"], mentions: false }, flow)
	const box = el.querySelector("textarea")
	vm.prefill("/")
	await nextTick()
	assert.ok(el.textContent.includes("start a fresh conversation"))
	vm.prefill("fix this /")
	await nextTick()
	assert.ok(el.textContent.includes("/skill:review"))
	assert.ok(!el.textContent.includes("start a fresh conversation"))
	// a slash no skill matches, like a path, opens nothing
	vm.prefill("see /usr")
	await nextTick()
	assert.ok(!el.querySelector("[data-palette-item]"))
	assert.ok(!el.textContent.includes("No matching commands"))

	vm.prefill("fix /re that")
	await nextTick()
	box.setSelectionRange(7, 7)
	box.dispatchEvent(new window.Event("click"))
	await nextTick()
	rowButton(el, "/skill:review").click()
	await nextTick()
	assert.equal(box.value, "fix /skill:review that")
	assert.equal(el.querySelector(".text-ink-blue-6").textContent, "/skill:review")

	// Escape closes the list and keeps what was typed
	vm.prefill("fix this /")
	await nextTick()
	box.dispatchEvent(new window.KeyboardEvent("keydown", { key: "Escape", bubbles: true }))
	await nextTick()
	assert.ok(!el.querySelector("[data-palette-item]"))
	assert.equal(box.value, "fix this /")
})

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
			prefs: { mode: "ask" }, sessionId: null, session: null, models: [], codeRefs: [], quotes: [], queued: [],
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
			prefs: { mode: "ask" }, sessionId: "s1", session: null, models: [], codeRefs: [], quotes: [], queued: [],
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

test("the queue steers or takes back a waiting message", async (t) => {
	const calls = []
	const flow = {
		options: { requireCwd: false, maxAttachments: 10, skillsEnabled: false },
		state: reactive({
			prefs: { mode: "ask" }, sessionId: "s1", session: null, models: [], codeRefs: [], quotes: [],
			queued: [{ key: "q1", label: "Also check this" }],
			skills: [], conversation: { running: true }, draft: null,
		}),
		sendQueued: (item) => calls.push(["send", item.key]),
		removeQueued: (item) => calls.push(["remove", item.key]),
	}
	const { el } = mount(t, Composer, { commands: [], mentions: false }, flow)
	const button = (text) => [...el.querySelectorAll("button")].find((b) => b.textContent.trim() === text)
	assert.match(el.textContent, /Queued\s*Also check this/)
	assert.ok(button("Steer").querySelector("[data-stub=FeatherIcon][name=corner-down-left]"))

	const box = el.querySelector("fieldset textarea")
	button("Steer").click()
	assert.equal(document.activeElement, box) // back to typing
	button("Steer").focus()
	el.querySelector("button[title='Remove from queue']").click()
	assert.equal(document.activeElement, box)
	assert.deepEqual(calls, [
		["send", "q1"],
		["remove", "q1"],
	])

	// a compaction takes no steering: the message can only be taken back
	flow.state.conversation.compacting = true
	await nextTick()
	assert.equal(button("Steer"), undefined)
	assert.ok(el.querySelector("button[title='Remove from queue']"))
	flow.state.conversation.compacting = false

	// no run to steer into: the same button sends it as the next turn
	flow.state.conversation.running = false
	await nextTick()
	assert.equal(button("Steer"), undefined)
	assert.ok(button("Send"))
})

test("the composer takes a host's placeholder and approval-mode copy", async (t) => {
	const flow = {
		options: { requireCwd: false, maxAttachments: 10, skillsEnabled: false },
		state: reactive({
			prefs: { mode: "ask" }, sessionId: null, session: null, models: [], codeRefs: [], quotes: [], queued: [],
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

test("selecting text in the thread shows Add to chat, which quotes it for the composer", async (t) => {
	t.mock.timers.enable({ apis: ["setTimeout"] })
	const boxes = { element: box(0, 0, 800, 600), range: box(100, 200, 300, 220) }
	measure(t, boxes)
	const conversation = reactive(initialConversation())
	applyEvent(conversation, { type: "user_message", seq: 1, ts: 10, content: "the daemon pins the list" })
	const quotes = []
	const flow = {
		options: {},
		state: reactive({ sessionId: "s1", loading: false, conversation }),
		addQuote: (text) => quotes.push(text),
	}
	const { el } = mount(t, MessageList, {}, flow)
	await nextTick()
	const pill = () => el.querySelector(".flow-add-to-chat")
	const select = (node) => {
		const range = document.createRange()
		range.selectNodeContents(node)
		document.getSelection().removeAllRanges()
		document.getSelection().addRange(range)
		t.mock.timers.tick(150) // jsdom's queued selectionchange arms the pill
		t.mock.timers.tick(150) // the debounce
		return nextTick()
	}

	await select(el.querySelector("[data-prompt-key] .whitespace-pre-wrap"))
	assert.equal(pill().textContent.trim(), "Add to chat")
	// centered over the selection, sitting above it
	assert.equal(pill().style.left, "200px")
	assert.equal(pill().style.top, "200px")
	assert.ok(pill().style.transform.includes("-100%"))

	// scrolled out of view, the selection takes the pill with it; scrolled back, it returns
	boxes.range = box(100, -40, 300, -20)
	document.dispatchEvent(new window.Event("scroll"))
	await nextTick()
	assert.equal(pill(), null)
	// back near the top, with no room above: it sits under the selection
	boxes.range = box(100, 10, 300, 30)
	document.dispatchEvent(new window.Event("scroll"))
	await nextTick()
	assert.equal(pill().style.top, "30px")
	assert.ok(!pill().style.transform.includes("-100%"))
	// a selection filling the view keeps the pill inside the list, not under the composer
	boxes.range = box(100, -40, 300, 900)
	document.dispatchEvent(new window.Event("scroll"))
	await nextTick()
	assert.equal(pill().style.top, "570px")

	pill().click()
	await nextTick()
	assert.deepEqual(quotes, ["the daemon pins the list"])
	assert.equal(document.getSelection().rangeCount, 0)
	assert.equal(pill(), null)

	// text outside the thread is not the thread's to quote
	const outside = document.createElement("p")
	outside.textContent = "elsewhere"
	document.body.append(outside)
	t.after(() => outside.remove())
	await select(outside)
	assert.equal(pill(), null)
})

test("a message's quotes show as quotes above its text", async (t) => {
	const conversation = reactive(initialConversation())
	applyEvent(conversation, {
		type: "user_message",
		seq: 1,
		ts: 10,
		content: "why?\n\n> pins the list\n> in place\n\n@/w/a.py:3",
	})
	const flow = { options: {}, state: reactive({ sessionId: "s1", loading: false, conversation }) }
	const { el } = mount(t, MessageList, {}, flow)
	await nextTick()
	const bubble = el.querySelector("[data-prompt-key]")
	assert.equal(bubble.querySelector("blockquote").textContent, "pins the list\nin place")
	assert.ok(bubble.textContent.includes("a.py (3)"))
	assert.ok(!bubble.textContent.includes(">"))
	assert.ok(bubble.querySelector(".whitespace-pre-wrap").textContent.endsWith("why?"))
})

test("the composer empties at once and spins the send button until sending succeeds", async (t) => {
	let finishSend
	let sent
	const flow = {
		options: { requireCwd: false, maxAttachments: 10, skillsEnabled: false },
		state: reactive({
			prefs: { mode: "ask" }, sessionId: "s1", session: null, models: [], codeRefs: [], quotes: [], queued: [],
			skills: [], conversation: { running: false }, draft: null,
		}),
		send(message, attachments) {
			sent = { message, attachments }
			return new Promise((resolve) => (finishSend = resolve))
		},
		clearCodeRefs() { this.state.codeRefs = [] },
		clearQuotes() { this.state.quotes = [] },
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
			prefs: { mode: "ask" }, sessionId: "s1", session: null, models: [], codeRefs: [], quotes: [], queued: [],
			skills: [], conversation: { running: false }, draft: null,
		}),
		async send() { return false },
		clearCodeRefs() { this.state.codeRefs = [] },
		clearQuotes() { this.state.quotes = [] },
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

test("a quote shows as a chip and travels under the message, before the code refs", async (t) => {
	let sent
	let finishSend
	const flow = {
		options: { requireCwd: false, maxAttachments: 10, skillsEnabled: false },
		state: reactive({
			prefs: { mode: "ask" }, sessionId: "s1", session: null, models: [], queued: [],
			codeRefs: [{ path: "/w/a.py", rel: "a.py", start: 3, end: 3 }], quotes: ["pins the list\nin place", "stale row"],
			skills: [], conversation: { running: false }, draft: null,
		}),
		send(message) {
			sent = message
			return new Promise((resolve) => (finishSend = resolve))
		},
		clearCodeRefs(went) { this.state.codeRefs = went ? this.state.codeRefs.filter((ref) => !went.includes(ref)) : [] },
		clearQuotes(went) { this.state.quotes = went ? this.state.quotes.filter((quote) => !went.includes(quote)) : [] },
		removeQuote(i) { this.state.quotes.splice(i, 1) },
		notify() {},
	}
	const { el, vm } = mount(t, Composer, { commands: [], mentions: false }, flow)
	await nextTick()
	const chips = () => [...el.querySelectorAll("[title]")].filter((node) => flow.state.quotes.includes(node.title))
	assert.equal(chips().length, 2)
	assert.equal(chips()[0].textContent.trim(), "pins the list in place") // one line; the full text is the title
	chips()[1].querySelector("button[title='Remove quote']").click()
	await nextTick()
	assert.deepEqual(flow.state.quotes, ["pins the list\nin place"])
	assert.equal(el.querySelector("button[title='Send']").disabled, false) // a quote alone can go

	vm.prefill("why?")
	el.querySelector("button[title='Send']").click()
	await nextTick()
	assert.equal(sent, "why?\n\n> pins the list\n> in place\n\n@a.py:3")
	// staged while the send is still out: these outlive it
	flow.state.quotes.push("added meanwhile")
	flow.state.codeRefs.push({ path: "/w/b.py", rel: "b.py", start: 1, end: 1 })
	finishSend(true)
	await new Promise((resolve) => setImmediate(resolve))
	assert.deepEqual(flow.state.quotes, ["added meanwhile"])
	assert.deepEqual(flow.state.codeRefs.map((ref) => ref.rel), ["b.py"])
})

test("a rewound message brings its quotes and code references back as chips", async (t) => {
	const flow = {
		options: { requireCwd: false, maxAttachments: 10, skillsEnabled: false },
		state: reactive({
			prefs: { mode: "ask" }, sessionId: "s1", session: null, models: [], queued: [], codeRefs: [], quotes: ["stale"],
			skills: [], conversation: { running: false }, draft: null,
		}),
		addCodeRef(path, start, end) { this.state.codeRefs.push({ path, rel: path, start, end }) },
		addQuote(text) { this.state.quotes.push(text) },
		clearCodeRefs() { this.state.codeRefs = [] },
		clearQuotes() { this.state.quotes = [] },
		setDraft(draft) { this.state.draft = draft },
		notify() {},
	}
	const { el } = mount(t, Composer, { commands: [], mentions: false }, flow)
	flow.state.draft = { text: "why?\n\n> pins the list\n\n@a.py:3-4", attachments: [] }
	await nextTick()
	assert.equal(el.querySelector("textarea").value, "why?")
	assert.deepEqual(flow.state.quotes, ["pins the list"])
	assert.deepEqual(flow.state.codeRefs, [{ path: "a.py", rel: "a.py", start: 3, end: 4 }])
	assert.equal(flow.state.draft, null)
})

function preparingComposer(t) {
	const requests = []
	const sent = []
	const discarded = []
	const flow = {
		options: { requireCwd: false, maxAttachments: 10, skillsEnabled: false },
		state: reactive({
			prefs: { mode: "ask", lastModel: "GPT" }, sessionId: null, session: null, models: [], codeRefs: [],
			quotes: [], queued: [], skills: [], conversation: { running: false }, draft: null,
		}),
		prepareAttachment(file, model) {
			return new Promise((resolve, reject) => requests.push({ file, model, resolve, reject }))
		},
		async discardAttachments(ids) { discarded.push(...ids) },
		async send(text, items) { sent.push({ text, ids: items.map((item) => item.id) }); return true },
		clearCodeRefs() { this.state.codeRefs = [] },
		clearQuotes() { this.state.quotes = [] },
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
	assert.equal(requests[0].model, "GPT")
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

test("a session that is still loading says so instead of showing a blank thread", async (t) => {
	const conversation = reactive(initialConversation())
	const flow = { options: {}, state: reactive({ sessionId: "s1", loading: true, conversation }) }
	const { el } = mount(t, MessageList, {}, flow)
	assert.ok(el.textContent.includes("Loading"))
	assert.ok(!el.textContent.includes("What would you like to build?"))

	// a first message in flight keeps its bubble and status while the new session loads
	conversation.sending = [{ key: "sending:1", entry: { type: "user_message", content: [{ type: "text", text: "hi" }], ts: 1 } }]
	await nextTick()
	assert.ok(!el.textContent.includes("Loading"))
	assert.ok(el.textContent.includes("Working"))

	conversation.sending = []
	flow.state.loading = false
	await nextTick()
	assert.ok(!el.textContent.includes("Loading"))
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
			prefs: { mode: "ask" }, sessionId: null, session: null, models: [], codeRefs: [], quotes: [], queued: [],
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
			prefs: { mode: "ask" }, sessionId: null, session: null, models: [], codeRefs: [], quotes: [], queued: [],
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

test("skill commands anywhere in a bubble stay blue", async (t) => {
	const { createFlowStore } = await import("../src/store.js")
	const UserBubble = await loadComponent("UserBubble")
	const store = createFlowStore({}, { requireCwd: false, skillsEnabled: false })
	const block = (name) => `<skill name="${name}" location="/skills/${name}/SKILL.md">\nbody\n</skill>`
	const content = `${block("review")}\n\n${block("tests")}\n\ncheck /skill:review then /skill:tests`
	const sent = mount(t, UserBubble, { entry: { type: "user_message", seq: 2, content } }, store)
	assert.deepEqual([...sent.el.querySelectorAll(".text-ink-blue-6")].map((span) => span.textContent), [
		"/skill:review",
		"/skill:tests",
	])
	// a bubble still sending has no expansion yet, so the catalog decides
	store.state.skills = [{ name: "review", description: "" }]
	const sending = mount(t, UserBubble, { entry: { type: "user_message", content: "please /skill:review /skill:nope" } }, store)
	assert.deepEqual([...sending.el.querySelectorAll(".text-ink-blue-6")].map((span) => span.textContent), ["/skill:review"])
})

function rowButton(el, text) {
	return [...el.querySelectorAll("button")].find((button) => button.textContent.includes(text))
}

test("a steered message waits below the running turn, Working under it, the turn still live above", async (t) => {
	const conversation = reactive(initialConversation())
	applyEvent(conversation, { type: "run_started", seq: 1, ts: 10 })
	applyEvent(conversation, { type: "user_message", seq: 2, ts: 10, content: "list files" })
	applyEvent(conversation, { type: "tool_call_display_ready", id: "call-1", name: "bash", arguments: { command: "ls" } })
	conversation.steering.push({ key: "steering:1", entry: { type: "user_message", content: "only src", ts: 11 } })
	const flow = { options: {}, state: reactive({ sessionId: "s1", loading: false, conversation }) }
	const { el } = mount(t, MessageList, {}, flow)
	await nextTick()

	const bubble = el.querySelector("[data-prompt-key='steering:1']")
	const liveTool = el.querySelector(".flow-tool-live")
	assert.ok(liveTool)
	assert.ok(bubble.compareDocumentPosition(liveTool) & bubble.DOCUMENT_POSITION_PRECEDING)
	assert.equal(bubble.nextElementSibling.textContent.trim(), "Working")

	// the turn's own status stays with the turn
	conversation.liveLabel = "Thinking"
	await nextTick()
	assert.equal(bubble.nextElementSibling.textContent.trim(), "Working")
})

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

test("a streaming table keeps its scroll box as rows and text arrive", async (t) => {
	const props = reactive({ text: "| a | b |\n| --- | --- |\n| 1 | 2 |" })
	const { el } = mount(t, { render: () => h(MarkdownContent, props) }, {}, {})
	const box = el.querySelector(".flow-md-table")
	props.text += "\n| 3 | 4 |\n\nAfter the table"
	await nextTick()
	assert.equal(el.querySelector(".flow-md-table"), box)
	assert.equal(box.querySelectorAll("tbody tr").length, 2)
	assert.ok(el.textContent.includes("After the table"))
})

test("a click doesn't focus the thread's buttons, links or summaries, so a closing dialog can't scroll back to one", async (t) => {
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
	applyEvent(conversation, { type: "assistant_message", seq: 5, ts: 13, content: [{ type: "text", text: "One file." }], stop_reason: "stop" })
	applyEvent(conversation, { type: "run_ended", seq: 6, ts: 13, reason: "done" })
	const flow = { options: {}, state: reactive({ sessionId: "s1", loading: false, conversation }) }
	const { el } = mount(t, MessageList, {}, flow)
	await nextTick()
	// false once a handler cancels the press, which is what stops the browser focusing
	const press = (target) => target.dispatchEvent(new window.MouseEvent("mousedown", { bubbles: true, cancelable: true }))
	assert.equal(press(el.querySelector("[data-turn-fold] span")), false)
	// links in replies and summaries in host tool views take focus on click too
	const thread = el.querySelector(".flow-thread")
	thread.insertAdjacentHTML("beforeend", '<a href="#x">docs</a><details><summary>Fields</summary></details>')
	assert.equal(press(thread.querySelector("a[href]")), false)
	assert.equal(press(thread.querySelector("summary")), false)
	assert.equal(press(thread), true)
})

// A finished thread scrolled to its bottom. jsdom has no layout, so the list's scroll
// geometry is faked (scrollTop clamps like a browser's) and resizes are reported by hand.
async function bottomedList(t) {
	const observers = []
	globalThis.ResizeObserver = class {
		constructor(callback) {
			this.callback = callback
			this.targets = new Set()
			observers.push(this)
		}
		observe(target) {
			this.targets.add(target)
		}
		disconnect() {
			this.targets.clear()
		}
	}
	t.after(() => delete globalThis.ResizeObserver)
	const conversation = reactive(initialConversation())
	applyEvent(conversation, { type: "user_message", seq: 1, ts: 10, content: "wait what" })
	applyEvent(conversation, { type: "assistant_message", seq: 2, ts: 11, content: [{ type: "text", text: "Context." }], stop_reason: "stop" })
	const flow = { options: {}, state: reactive({ sessionId: "s1", loading: false, conversation }) }
	const { el } = mount(t, MessageList, {}, flow)
	await nextTick()
	const thread = el.querySelector(".flow-thread")
	const list = thread.parentElement
	const box = { height: 2165, top: 0 }
	Object.defineProperty(list, "clientHeight", { get: () => 816 })
	Object.defineProperty(list, "scrollHeight", { get: () => box.height })
	Object.defineProperty(list, "scrollTop", {
		get: () => box.top,
		set: (value) => (box.top = Math.max(0, Math.min(value, box.height - 816))),
	})
	const scrolled = () => list.dispatchEvent(new window.Event("scroll"))
	const resize = (...targets) => {
		for (const observer of observers) {
			const entries = targets.filter((target) => observer.targets.has(target)).map((target) => ({ target }))
			if (entries.length) observer.callback(entries)
		}
	}
	list.scrollTop = box.height
	scrolled()
	return { el, list, thread, box, scrolled, resize }
}

test("a view on the bottom stays there when a panel or the window resizes the list", async (t) => {
	const { el, list, thread, box, scrolled, resize } = await bottomedList(t)

	// a panel opens: the text re-wraps taller and the browser keeps the visible lines in place
	box.height = 2325
	list.scrollTop += 107
	resize(list, thread)
	scrolled()
	assert.equal(list.scrollTop, 2325 - 816)

	// a slight widening: the browser moves the view up with the lines it keeps in place
	box.height = 2245
	list.scrollTop -= 54
	resize(list, thread)
	scrolled()
	await nextTick()
	assert.equal(list.scrollTop, 2245 - 816)
	assert.equal(el.querySelector("button[title='Scroll to bottom']"), null)
})

test("a resize leaves a view that an opened row pushed off the bottom where it is", async (t) => {
	const { list, thread, box, resize } = await bottomedList(t)
	box.height = 2400 // a row opened below the view
	resize(thread)
	box.height = 2480 // then a panel opens
	resize(list, thread)
	assert.equal(list.scrollTop, 2165 - 816)
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
	assert.equal(el.querySelector("h2").textContent, "Default preset") // the form stays open
	assert.ok(save().disabled)
	el.querySelector("button[title='Back to presets']").click()
	await nextTick()
	assert.match(el.textContent, /3 of 3 tools/)
})

test("a new preset stays open after saving, as an edit of itself", async (t) => {
	const { createFlowStore } = await import("../src/store.js")
	const SettingsPresets = await loadComponent("SettingsPresets")
	globalThis.localStorage = { getItem: () => null, setItem() {} }
	t.after(() => delete globalThis.localStorage)
	const store = createFlowStore({}, { requireCwd: false, skillsEnabled: false })
	const { el } = mount(t, SettingsPresets, {}, store)
	const button = (label) => [...el.querySelectorAll("button")].find((b) => b.textContent === label)
	const type = (field, value) => {
		field.value = value
		field.dispatchEvent(new window.Event("input"))
		return nextTick()
	}

	button("New preset").click()
	await nextTick()
	await type(el.querySelector("input"), "Reviewer ")
	button("Save").click()
	await nextTick()
	assert.equal(el.querySelector("h2").textContent, "Edit preset")
	assert.equal(el.querySelector("input").value, "Reviewer")
	assert.ok(button("Save").disabled)
	assert.ok(button("Delete"))

	await type(el.querySelector("textarea"), "Be brief.")
	button("Save").click()
	await nextTick()
	assert.deepEqual(store.state.presets.map((p) => [p.name, p.prompt]), [["Reviewer", "Be brief."]]) // updated, not a second preset
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

test("a closed workspace panel is inert, so its hidden buttons can't take focus", async (t) => {
	const workspace = reactive({ open: false, maximized: false, view: null, active: null, tabs: [] })
	const flow = { options: {}, state: reactive({ sessionId: "s1", loading: false, workspace, prefs: {} }) }
	const { el } = mount(t, WorkspacePanel, {}, flow)
	await nextTick()
	const aside = el.querySelector("aside")
	assert.ok(aside.hasAttribute("inert"))

	workspace.open = true
	await nextTick()
	assert.ok(!aside.hasAttribute("inert"))
})

const settle = () => new Promise((resolve) => setImmediate(resolve))

// types into the files bar's search box, short of the debounce
async function typeQuery(el, query) {
	const input = el.querySelector("input")
	input.value = query
	input.dispatchEvent(new window.Event("input"))
	await nextTick()
}

// types a query and lets its debounced search land
async function typeSearch(t, el, query) {
	await typeQuery(el, query)
	t.mock.timers.tick(200) // the query's debounce
	await settle()
}

const press = (el, key) => el.dispatchEvent(new window.KeyboardEvent("keydown", { key }))

test("a folder in the file search results folds and unfolds, and stays folded until the search is cleared", async (t) => {
	t.mock.timers.enable({ apis: ["setTimeout"] })
	const results = { o: ["src/a/one.js", "src/two.js", "top.js"], on: ["src/a/one.js", "src/one.md"] }
	const flow = {
		state: reactive({ workspace: { tabs: [], active: null }, prefs: {} }),
		explorerCwd: () => "/w",
		listFiles: async () => ({ path: "/w", entries: [] }),
		searchFiles: async (query) => ({ path: "/w", matches: results[query], truncated: false }),
	}
	const { el } = mount(t, FilesBar, { open: true, mode: "files" }, flow)
	const search = (query) => typeSearch(t, el, query)
	const row = (path) => el.querySelector(`[title='/w/${path}']`)
	const rows = () => [...el.querySelectorAll("[title^='/w/']")].map((r) => r.textContent.trim())
	const toggle = async (path) => {
		row(path).click()
		await nextTick()
	}

	await search("o")
	assert.deepEqual(rows(), ["src", "a", "one.js", "two.js", "top.js"])
	await toggle("src/a")
	assert.deepEqual(rows(), ["src", "a", "two.js", "top.js"])
	assert.equal(row("src/a").querySelector("[data-stub=FeatherIcon]").getAttribute("name"), "chevron-right")
	// a screen reader hears whether a folder is open; a file has nothing to say
	assert.equal(row("src/a").getAttribute("aria-expanded"), "false")
	assert.equal(row("src").getAttribute("aria-expanded"), "true")
	assert.equal(row("top.js").hasAttribute("aria-expanded"), false)
	press(row("src"), "Enter")
	await nextTick()
	assert.deepEqual(rows(), ["src", "top.js"])
	press(row("src"), " ")
	await nextTick()
	assert.deepEqual(rows(), ["src", "a", "two.js", "top.js"]) // the inner fold outlives its parent's

	await search("on")
	assert.deepEqual(rows(), ["src", "a", "one.md"]) // refining the query keeps folds
	await search("")
	await search("on")
	assert.deepEqual(rows(), ["src", "a", "one.js", "one.md"]) // a new search starts open

	// emptied and retyped inside the debounce: the search never sees the empty box
	await toggle("src/a")
	await typeQuery(el, "")
	await search("o")
	assert.deepEqual(rows(), ["src", "a", "one.js", "two.js", "top.js"])
})

test("a folder in the file tree opens with Space, says it's open, and stays open through a search", async (t) => {
	t.mock.timers.enable({ apis: ["setTimeout"] })
	const dirs = { "": [{ name: "src", type: "dir" }], "/w/src": [{ name: "a.js", type: "file" }] }
	const flow = {
		state: reactive({ workspace: { tabs: [], active: null }, prefs: {} }),
		explorerCwd: () => "/w",
		listFiles: async (path = "") => ({ path: path || "/w", entries: dirs[path] }),
		searchFiles: async () => ({ path: "/w", matches: ["src/a.js"], truncated: false }),
	}
	const { el } = mount(t, FilesBar, { open: true, mode: "files" }, flow)
	const shown = (path) =>
		[...el.querySelectorAll(`[title='${path}']`)].filter((r) => !r.closest("[style*='display: none']"))
	await settle()
	const folder = el.querySelector("[title='/w/src']")
	assert.equal(folder.getAttribute("aria-expanded"), "false")
	press(folder, " ")
	await settle()
	assert.equal(folder.getAttribute("aria-expanded"), "true")
	assert.equal(shown("/w/src/a.js").length, 1)

	await typeSearch(t, el, "a")
	assert.equal(shown("/w/src").length, 1) // the results only; the tree is out of sight
	await typeSearch(t, el, "")
	assert.equal(shown("/w/src/a.js").length, 1)
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
			prefs: { mode: "ask" }, sessionId: "s1", session: null, models: [], codeRefs: [], quotes: [], queued: [],
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

test("the transcript shows each step as raw JSON, with usage under its request", async (t) => {
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
	assert.match(panel.textContent, /user\s*\{\s*"type": "user_message",\s*"content": "find the leak"\s*\}/)
	assert.match(panel.textContent, /assistant\s*\{\s*"type": "assistant_message".*\}\s*usage\s*\{\s*"type": "usage",.*"input_tokens": 1000/s)
	// every tool reads the same way: the call, then what it returned
	assert.match(panel.textContent, /tool\s*input\s*\{\s*"type": "tool_call".*"path": "server\.py".*output\s*\{\s*"type": "tool_result".*"content": "leaky line"/s)
	assert.doesNotMatch(panel.textContent, /"seq"|"context_window"/) // Flow's own fields stay out
	assert.doesNotMatch(panel.textContent, /estimated|reported|~4|prompt & tool definitions/)
	assert.equal(panel.querySelectorAll("button").length, 1) // only the close button
})

test("the chat list says it is loading, not that there are no chats or matches", async (t) => {
	t.mock.timers.enable({ apis: ["setTimeout"] })
	const flow = {
		options: {},
		state: reactive({ sessions: [], sessionsLoading: true, sessionsMore: false, sessionId: null, prefs: {} }),
		sessionTitle: (session) => session.title,
		// past a full page, a search goes to the host
		searchSessions() {
			flow.state.sessionsLoading = true
		},
	}
	const { el } = mount(t, SessionSidebar, {}, flow)
	assert.ok(el.textContent.includes("Loading"))
	assert.ok(!el.textContent.includes("No chats yet"))
	flow.state.sessionsLoading = false
	await nextTick()
	assert.ok(!el.textContent.includes("Loading"))
	assert.ok(el.textContent.includes("No chats yet"))

	flow.state.sessions = [{ session_id: "s1", title: "Alpha" }]
	await typeSearch(t, el, "beta")
	assert.ok(el.textContent.includes("Loading"))
	assert.ok(!el.textContent.includes("No matches"))
	flow.state.sessionsLoading = false
	await nextTick()
	assert.ok(el.textContent.includes("No matches"))
})

test("the model list says it is loading, not that no provider is connected", async (t) => {
	const flow = { state: reactive({ models: [], modelsLoading: true, conversation: {}, prefs: {} }) }
	const { el } = mount(t, ModelPalette, {}, flow)
	assert.ok(el.textContent.includes("Loading"))
	assert.ok(!el.textContent.includes("No models yet"))
	flow.state.modelsLoading = false
	await nextTick()
	assert.ok(!el.textContent.includes("Loading"))
	assert.ok(el.textContent.includes("No models yet"))
})

test("the file picker says it is loading until its first listing arrives", async (t) => {
	let answer
	const flow = {
		explorerCwd: () => "/w",
		listFiles: () => new Promise((resolve) => (answer = resolve)),
	}
	const { el } = mount(t, FileMentionPalette, {}, flow)
	assert.ok(el.textContent.includes("Loading"))
	answer({ path: "/w", entries: [] })
	await settle()
	assert.ok(!el.textContent.includes("Loading"))
	assert.ok(el.textContent.includes("No files here"))
})

test("the files panel says it is loading until its tree or change list arrives", async (t) => {
	t.mock.timers.enable({ apis: ["setTimeout"] })
	let list, changes
	const flow = {
		state: reactive({ workspace: { tabs: [], active: null }, prefs: {} }),
		explorerCwd: () => "/w",
		listFiles: () => new Promise((resolve) => (list = resolve)),
		gitChanges: () => new Promise((resolve) => (changes = resolve)),
	}
	const tree = mount(t, FilesBar, { open: true, mode: "files" }, flow)
	assert.ok(tree.el.textContent.includes("Loading"))
	list({ path: "/w", entries: [] })
	await settle()
	assert.ok(!tree.el.textContent.includes("Loading"))
	assert.ok(tree.el.textContent.includes("Empty folder"))

	const diff = mount(t, FilesBar, { open: true, mode: "diff" }, flow)
	assert.ok(diff.el.textContent.includes("Loading"))
	changes({ root: "/w", files: [] })
	await settle()
	assert.ok(!diff.el.textContent.includes("Loading"))
	assert.ok(diff.el.textContent.includes("No uncommitted changes"))

	// no folder to list, or a failed call: nothing keeps spinning
	const none = { ...flow, listFiles: async () => null, gitChanges: async () => null }
	const bare = mount(t, FilesBar, { open: true, mode: "files" }, none)
	const bareDiff = mount(t, FilesBar, { open: true, mode: "diff" }, none)
	await settle()
	assert.ok(!bare.el.textContent.includes("Loading"))
	assert.ok(!bareDiff.el.textContent.includes("Loading"))
})

test("the providers list says it is loading until it arrives", async (t) => {
	let answer
	const flow = { client: { providers: () => new Promise((resolve) => (answer = resolve)) } }
	const { el } = mount(t, ProvidersDialog, {}, flow)
	assert.ok(el.textContent.includes("Loading"))
	answer({ providers: [{ id: "openai", name: "OpenAI" }] })
	await settle()
	assert.ok(!el.textContent.includes("Loading"))
	assert.ok(el.textContent.includes("OpenAI"))
})

test("the skills settings say they are loading until the skill folders are read", async (t) => {
	let answer
	const flow = {
		state: reactive({ settingsOpen: true, sessionId: null, session: null, sessions: [], prefs: {} }),
		client: { skillFiles: () => new Promise((resolve) => (answer = resolve)) },
	}
	const { el } = mount(t, SettingsSkills, {}, flow)
	assert.ok(el.textContent.includes("Loading"))
	assert.ok(!el.textContent.includes("No global skills yet"))
	answer({ skills: [], roots: { global: "/g" } })
	await settle()
	assert.ok(!el.textContent.includes("Loading"))
	assert.ok(el.textContent.includes("No global skills yet"))
})

test("a sub-agent's tab says it is loading while its session loads, not that it is starting", async (t) => {
	const flow = { state: reactive({ loading: true, conversation: { subagents: {} } }) }
	const { el } = mount(t, SubagentView, { id: "a1" }, flow)
	assert.ok(el.textContent.includes("Loading"))
	assert.ok(!el.textContent.includes("Starting"))
	flow.state.loading = false
	await nextTick()
	assert.ok(!el.textContent.includes("Loading"))
	assert.ok(el.textContent.includes("Starting"))
})

test("the header says nothing while a chat loads, not that it is a new chat", async (t) => {
	const flow = {
		state: reactive({
			loading: false, sessionId: null, session: null, conversation: initialConversation(), prefs: {}, workspace: {},
		}),
	}
	const { el } = mount(t, ChatHeader, {}, flow)
	assert.ok(el.textContent.includes("New chat"))

	// a chat opened from its link: no title to seed until it arrives
	flow.state.sessionId = "s1"
	flow.state.loading = true
	await nextTick()
	assert.ok(!el.textContent.includes("New chat"))
	flow.state.session = { title: "Quarterly report" }
	flow.state.loading = false
	await nextTick()
	assert.ok(el.textContent.includes("Quarterly report"))
})

test("the model button never shows the last model picked while a chat loads", async (t) => {
	const conversation = reactive(initialConversation())
	const flow = { state: reactive({ loading: true, conversation, prefs: { lastModel: "openai/gpt-old" } }) }
	const { el } = mount(t, ModelButton, {}, flow)
	assert.ok(!el.textContent.includes("gpt-old"))
	assert.ok(!el.textContent.includes("Choose Model"))
	conversation.model = "openai/gpt-6" // the chat's own, from the list or the loaded session
	await nextTick()
	assert.ok(el.textContent.includes("gpt-6"))
})

test("a file search in flight shows the spinner with its own word", async (t) => {
	t.mock.timers.enable({ apis: ["setTimeout"] })
	const flow = {
		state: reactive({ workspace: { tabs: [], active: null }, prefs: {} }),
		explorerCwd: () => "/w",
		listFiles: async () => ({ path: "/w", entries: [] }),
		searchFiles: () => new Promise(() => {}),
	}
	const { el } = mount(t, FilesBar, { open: true, mode: "files" }, flow)
	await typeSearch(t, el, "app")
	assert.ok(el.textContent.includes("Searching…"))
	assert.ok(el.querySelector("[data-stub=Spinner]"))
})
