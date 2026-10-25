import assert from "node:assert/strict"
import test from "node:test"

import { JSDOM } from "jsdom"

// Vue's DOM runtime captures document at import time.
const dom = new JSDOM("<body></body>", { url: "http://localhost" })
for (const name of ["window", "document", "Document", "Element", "SVGElement", "HTMLElement", "Node", "NodeFilter"]) {
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
const { dialog, dialogStack, loadComponent } = await import("./helpers/components.js")
const { applyEvent, initialConversation } = await import("../src/transcript.js")
const { FlowAPIError } = await import("../src/client.js")
const { layout } = await import("../src/layout.js")
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
const EditorView = await loadComponent("EditorView")
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
	let mounted = true
	const unmount = () => {
		if (mounted) app.unmount()
		mounted = false
	}
	t.after(() => {
		unmount()
		el.remove()
	})
	return { el, vm, unmount }
}

// jsdom measures nothing: a test that needs boxes stubs them for its duration
const box = (left, top, right, bottom) => ({ left, top, right, bottom, width: right - left, height: bottom - top })
function measure(t, boxes) {
	const protos = { element: dom.window.Element.prototype, range: dom.window.Range.prototype }
	const before = { element: protos.element.getBoundingClientRect, range: protos.range.getBoundingClientRect, lines: protos.range.getClientRects }
	for (const kind of ["element", "range"]) protos[kind].getBoundingClientRect = () => boxes[kind]
	// a text piece's line boxes: what the test lists for its text, else the range's one box
	protos.range.getClientRects = function () {
		if (!this.toString().trim()) return [] // collapsed, or whitespace between blocks
		return boxes.lines?.[this.startContainer.data] ?? [boxes.range]
	}
	t.after(() => {
		for (const kind of ["element", "range"]) protos[kind].getBoundingClientRect = before[kind]
		protos.range.getClientRects = before.lines
	})
}

test("a slash offers skills, mid-message only skills, and puts the one picked where it was typed; a host can turn them off", async (t) => {
	for (const enabled of [true, false]) {
		let loads = 0
		const flow = {
			options: { requireCwd: false, maxAttachments: 10, ...(enabled ? {} : { skillsEnabled: false }) },
			state: reactive({
				prefs: { mode: "ask" }, sessionId: null, session: null, models: [], codeRefs: [], quotes: [], queued: [],
				skills: [{ name: "review", description: "Review files" }], conversation: {}, draft: null,
			}),
			loadSkills() { loads++ },
		}
		const { vm, el } = mount(t, Composer, { commands: ["new"], mentions: false }, flow)
		// a new chat's load before any "/", so its first list opens whole
		assert.equal(loads, enabled ? 1 : 0)
		const box = el.querySelector("textarea")
		vm.prefill("/")
		await nextTick()
		assert.ok(el.textContent.includes("Start a fresh conversation"))
		// a skill row reads its name and description, not its /skill: form
		assert.equal(el.textContent.includes("Review files"), enabled)
		assert.ok(!el.textContent.includes("/skill:review"))
		assert.equal(loads, enabled ? 2 : 0)
		vm.prefill("/skill:review investigate")
		await nextTick()
		assert.equal(box.classList.contains("text-transparent"), enabled)
		if (!enabled) continue

		vm.prefill("fix this /")
		await nextTick()
		assert.ok(el.textContent.includes("Review files"))
		assert.ok(!el.textContent.includes("Start a fresh conversation"))
		// a slash no skill matches, like a path, opens nothing
		vm.prefill("see /usr")
		await nextTick()
		assert.ok(!el.querySelector("[data-palette-item]"))
		assert.ok(!el.textContent.includes("No matching commands"))

		vm.prefill("fix /re that")
		await nextTick()
		const loaded = loads
		box.setSelectionRange(7, 7)
		box.dispatchEvent(new window.Event("click"))
		await nextTick()
		// a slash the caret reaches loads them too, as a typed "/" does once the caret passes it
		assert.equal(loads, loaded + 1)
		rowButton(el, "Review files").click()
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
	}
})

const ArgsView = {
	props: ["arguments"],
	setup: (props) => () => h("dl", { "data-test": "args" }, [
		h("dt", "Status"), h("dd", props.arguments.fields.status),
	]),
}
const args = { fields: { status: "Paid" } }

const ResultView = {
	props: ["arguments", "result"],
	setup: (props) => () => h("table", { "data-test": "result" }, [
		h("tr", [h("td", props.arguments.fields.status), h("td", props.result.content)]),
	]),
}

test("an opened tool row shows its output, or a host's views of its arguments and result", async (t) => {
	// no host: the call's display segments, and its output once opened
	const bash = { call: { id: "bash", name: "bash", arguments: { command: "pwd" },
		display: [{ text: "Running " }, { text: "pwd", arg: "command" }],
	}, result: { content: "/project" } }
	const { el } = mount(t, ToolGroup, { steps: [bash] }, { state: {} })
	assert.ok(el.textContent.includes("Running pwd"))
	assert.equal(el.querySelector("pre"), null)
	el.querySelector("button").click()
	await nextTick()
	assert.equal(el.querySelector("pre").textContent, "/project")
	assert.equal(el.querySelector("[data-test=args]"), null)

	// a host's argument view shows before the result, and stays above the output once it lands
	const step = reactive({ call: { id: "c1", name: "update_document", arguments: args } })
	const host = mount(t, ToolGroup, { steps: [step] }, { options: { presentTool: () => ({ argsComponent: ArgsView }) }, state: {} })
	host.el.querySelector("button").click()
	await nextTick()
	assert.equal(host.el.querySelector("[data-test=args] dd").textContent, "Paid")
	assert.equal(host.el.querySelector("pre"), null)
	step.result = { content: "Document updated" }
	await nextTick()
	assert.equal(host.el.querySelector("[data-test=args] dd").textContent, "Paid")
	assert.equal(host.el.querySelector("pre").textContent, "Document updated")

	// a host's own result view and stat take the place of both
	const viewed = reactive({ call: { id: "c1", name: "update_document", arguments: args } })
	const presentTool = (name, callArgs, result) => ({
		argsComponent: ArgsView,
		resultComponent: ResultView,
		stat: result ? "3 updated" : "",
	})
	const own = mount(t, ToolGroup, { steps: [viewed] }, { options: { presentTool }, state: {} })
	own.el.querySelector("button").click()
	await nextTick()
	assert.equal(own.el.querySelector("[data-test=args] dd").textContent, "Paid")
	viewed.result = { content: "3 records" }
	await nextTick()
	assert.equal(own.el.querySelector("[data-test=result] td").textContent, "Paid")
	assert.equal(own.el.querySelector("[data-test=args]"), null)
	assert.equal(own.el.querySelector("pre"), null)
	assert.ok(own.el.textContent.includes("3 updated"))
})

test("an approval card names the call and shows what it will do, in a host's own view if it has one", async (t) => {
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

	// without a host: the command it runs, the diff of an edit
	const calls = [
		{ id: "bash", name: "bash", args: { command: "pwd" } },
		{ id: "edit", name: "edit", args: { path: "a.txt", edits: [{ old: "before", new: "after" }] } },
	]
	const standalone = mount(t, { render: () => calls.map((call) => h(ApprovalCard, { call })) }, {}, { options: {} })
	assert.ok(standalone.el.textContent.includes("Run this command?"))
	assert.ok(standalone.el.textContent.includes("Apply 1 edit to a.txt?"))
	assert.ok(!standalone.el.textContent.includes(" of "), "a lone card carries no batch counter")
	assert.deepEqual([...standalone.el.querySelectorAll("pre")].map((pre) => pre.textContent), ["pwd", "- before+ after"])
})

test("a host picks a row's stat and dropdown, but the user's decision and an error outrank it", async (t) => {
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

	// no dropdown for a host's own lookups, name clash or not
	for (const [name, presented, expanded] of [
		["read", { resultComponent: ResultView }, true],
		["read", {}, false],
		["find_doctypes", { expandable: false }, false],
	]) {
		const lookup = { call: { id: "c1", name, arguments: args }, result: { content: "[]" } }
		const row = mount(t, ToolGroup, { steps: [lookup] }, { options: { presentTool: () => presented }, state: {} })
		assert.equal(!!row.el.querySelector("button"), expanded, `${name} ${JSON.stringify(presented)}`)
	}

	// an error always opens, its output in place of the host's result view
	const failed = { call: { id: "c1", name: "describe", arguments: args }, result: { content: "boom", is_error: true } }
	const error = mount(t, ToolGroup, { steps: [failed] }, {
		options: { presentTool: () => ({ resultComponent: ResultView, expandable: false }) },
		state: {},
	})
	error.el.querySelector("button").click()
	await nextTick()
	assert.equal(error.el.querySelector("pre").textContent, "boom")
	assert.equal(error.el.querySelector("[data-test=result]"), null)
})

test("a host's empty state and turn actions take the list's place", async (t) => {
	const TurnActions = {
		props: ["turnKey", "text", "ts"],
		setup: (props) => () => h("span", { "data-test": "actions" }, `${props.turnKey}:${props.text}`),
	}
	const conversation = reactive({
		entries: [], partial: [], running: false, pendingApproval: null, liveLabel: null, liveErrorSeqs: [],
	})
	const flow = {
		options: { turnActions: TurnActions },
		state: reactive({ sessionId: "s1", loading: false, conversation }),
	}
	const { el } = mount(t, {
		render: () => h(MessageList, null, { empty: () => h("h2", { "data-test": "empty" }, "How can I help?") }),
	}, {}, flow)
	assert.equal(el.querySelector("[data-test=empty]").textContent, "How can I help?")
	assert.ok(!el.textContent.includes("What would you like to build?"))

	conversation.entries.push(
		{ type: "user_message", seq: 2, content: "hi", ts: 10 },
		{ type: "assistant_message", seq: 3, content: [{ type: "text", text: "hello" }], ts: 11 },
	)
	await nextTick()
	assert.equal(el.querySelector("[data-test=actions]")?.textContent, "turn:2:hello")
	const bare = mount(t, MessageList, {}, { options: {}, state: flow.state })
	await nextTick()
	assert.equal(bare.el.querySelector("[data-test=actions]"), null)
})

test("a host fills the composer with its pickers, commands, palette pages and words, and can make it all inert", async (t) => {
	const flow = {
		options: { requireCwd: false, maxAttachments: 10, skillsEnabled: false },
		state: reactive({
			prefs: { mode: "ask" }, sessionId: null, session: null, models: [], codeRefs: [], quotes: [], queued: [],
			skills: [], conversation: {}, draft: null,
		}),
		setMode: (mode) => (flow.state.prefs.mode = mode),
	}
	const bare = mount(t, Composer, { commands: [], mentions: false }, flow)
	assert.ok(bare.el.querySelector("button[title^='Choose Model']"))

	const commands = [{ name: "agents", label: "Agent", icon: "user", hint: "choose the agent", view: "agents" }, "model"]
	const modes = [
		{ id: "ask", label: "Ask first", desc: "Pauses before documents change." },
		{ id: "auto", label: "Just do it", desc: "Never asks." },
	]
	const host = reactive({ disabled: false })
	const { el, vm } = mount(t, {
		render: () => h(Composer, { ref: "composer", commands, mentions: false, placeholder: "Ask Sales…", modes, disabled: host.disabled }, {
			toolbar: ({ openPalette }) => [
				h("button", { "data-test": "agent", onClick: () => openPalette("thinking") }, "Agent"),
				h(ModelButton, { onOpen: openPalette }),
			],
			palette: ({ view, query, close }) =>
				view === "agents" ? h("div", { "data-test": "host-palette", onClick: close }, `${view}:${query}`) : null,
		}),
	}, {}, flow)
	const agent = el.querySelector("[data-test=agent]")
	const model = el.querySelector("button[title^='Choose Model']")
	// the approval mode by the attach button, the pickers by Send
	const order = ["button[title='Attach images']", "button[title='Approval mode']", "[data-test=agent]", "button[title^='Choose Model']", "button[title=Send]"]
	const placed = order.map((selector) => el.querySelector(selector))
	placed.slice(1).forEach((node, i) => assert.ok(placed[i].compareDocumentPosition(node) & Node.DOCUMENT_POSITION_FOLLOWING, order[i + 1]))
	assert.equal(el.querySelector("[data-stub=ThinkingPalette]"), null)
	agent.click()
	await nextTick()
	assert.ok(el.querySelector("[data-stub=ThinkingPalette]"))
	// a picker opened over an empty composer searches with it, and its "/" goes when it closes
	const box = el.querySelector("textarea")
	assert.equal(box.value, "/")
	el.querySelector("[data-stub=ThinkingPalette]").dispatchEvent(new window.Event("close"))
	await nextTick()
	assert.equal(box.value, "")

	// the model button's lists are its own, hung from it, one line a row: the composer's stay shut
	model.click()
	await nextTick()
	const picker = model.parentElement
	const entries = [...picker.querySelectorAll("[data-palette-item]")].map((row) => [...row.querySelectorAll("span")].map((span) => span.textContent))
	assert.deepEqual(entries, [["Model", "Choose Model"], ["Thinking", "Default"]])
	picker.querySelector("[data-palette-item]").click()
	await nextTick()
	assert.equal(picker.querySelector("[data-palette-item]"), null)
	assert.ok(picker.querySelector("[data-stub=ModelPalette]"))
	assert.equal(box.value, "")
	picker.querySelector("[data-stub=ModelPalette]").dispatchEvent(new window.Event("close"))
	await nextTick()
	assert.equal(picker.querySelector("[data-stub=ModelPalette]"), null)
	assert.equal(el.querySelector("[data-stub=ModelPalette]"), null)

	// the host's own command opens its palette slot
	vm.$refs.composer.prefill("/")
	await nextTick()
	// the host's command first, each row its label and what it does
	const rows = [...el.querySelectorAll("[data-palette-item]")]
	assert.deepEqual(rows.map((row) => [...row.querySelectorAll("span")].map((span) => span.textContent)), [
		["Agent", "choose the agent"],
		["Model", "Choose the model"],
	])
	el.querySelector("[data-palette-item]").click()
	await nextTick()
	// the page searches with the composer's text after its "/"
	assert.equal(el.querySelector("[data-test=host-palette]").textContent, "agents:")
	vm.$refs.composer.prefill("/sa")
	await nextTick()
	assert.equal(el.querySelector("[data-test=host-palette]").textContent, "agents:sa")
	// Backspace on the bare "/" goes back to the commands, keeping the "/"
	vm.$refs.composer.prefill("/")
	await nextTick()
	box.dispatchEvent(new window.KeyboardEvent("keydown", { key: "Backspace", bubbles: true, cancelable: true }))
	await nextTick()
	assert.equal(el.querySelector("[data-test=host-palette]"), null)
	assert.equal(box.value, "/")
	assert.equal(el.querySelectorAll("[data-palette-item]").length, 2)
	el.querySelector("[data-palette-item]").click()
	await nextTick()
	el.querySelector("[data-test=host-palette]").click()
	await nextTick()
	assert.equal(el.querySelector("[data-test=host-palette]"), null)
	assert.equal(box.value, "")
	// a "/command" at the head of a draft opens its page unfiltered, and the draft outlives it
	vm.$refs.composer.prefill("/ag\nplease fix the login bug")
	await nextTick()
	box.setSelectionRange(3, 3)
	box.dispatchEvent(new window.Event("select"))
	await nextTick()
	el.querySelector("[data-palette-item]").click()
	await nextTick()
	assert.equal(el.querySelector("[data-test=host-palette]").textContent, "agents:")
	el.querySelector("[data-test=host-palette]").click()
	await nextTick()
	assert.equal(box.value, "\nplease fix the login bug")
	// one after spaces alone is all the box holds: its page searches from a bare "/"
	vm.$refs.composer.prefill("  /ag")
	await nextTick()
	el.querySelector("[data-palette-item]").click()
	await nextTick()
	assert.equal(el.querySelector("[data-test=host-palette]").textContent, "agents:")
	assert.equal(box.value, "/")
	el.querySelector("[data-test=host-palette]").click()
	await nextTick()
	// back from a toolbar picker over a "/" whose list Escape put away brings the commands back
	vm.$refs.composer.prefill("/")
	await nextTick()
	box.dispatchEvent(new window.KeyboardEvent("keydown", { key: "Escape", bubbles: true, cancelable: true }))
	await nextTick()
	assert.equal(el.querySelectorAll("[data-palette-item]").length, 0)
	agent.click()
	await nextTick()
	box.dispatchEvent(new window.KeyboardEvent("keydown", { key: "Backspace", bubbles: true, cancelable: true }))
	await nextTick()
	assert.equal(el.querySelectorAll("[data-palette-item]").length, 2)
	box.dispatchEvent(new window.KeyboardEvent("keydown", { key: "Escape", bubbles: true, cancelable: true }))
	vm.$refs.composer.prefill("")
	await nextTick()

	assert.equal(el.querySelector("textarea").placeholder, "Ask Sales…")
	const mode = el.querySelector("button[title='Approval mode']")
	assert.equal(mode.textContent.trim(), "Ask first")
	mode.click()
	await nextTick()
	// a row a mode, what it does under its name, the one in force ticked
	const modeRows = [...mode.parentElement.querySelectorAll("[data-palette-item]")]
	assert.deepEqual(modeRows.map((row) => [[...row.querySelectorAll(":scope > span > span")].map((span) => span.textContent), row.getAttribute("aria-current")]), [
		[["Ask first", "Pauses before documents change."], "true"],
		[["Just do it", "Never asks."], null],
	])
	modeRows[1].click()
	await nextTick()
	assert.equal(mode.parentElement.querySelector("[data-palette-item]"), null)
	assert.equal(mode.textContent.trim(), "Just do it")

	// a narrow frame shows the mode as its icon, named in its title; its list puts each icon by its mode
	layout.narrow = true
	t.after(() => (layout.narrow = false))
	await nextTick()
	const icon = (node) => node.querySelector("[data-stub=FeatherIcon]")?.getAttribute("name")
	assert.equal(mode.title, "Approval mode: Just do it")
	assert.deepEqual([mode.textContent.trim(), icon(mode)], ["", "unlock"])
	mode.click()
	await nextTick()
	assert.deepEqual([...mode.parentElement.querySelectorAll("[data-palette-item]")].map(icon), ["lock", "unlock"])
	mode.click()
	layout.narrow = false
	await nextTick()

	// disabled, it is shown but inert, the host's pickers included
	host.disabled = true
	await nextTick()
	assert.ok(el.querySelector("textarea").matches(":disabled"))
	assert.ok(el.querySelector("button[title='Send']").matches(":disabled"))
	assert.ok(el.querySelector("[data-test=agent]").matches(":disabled"))
})

test("the composer asks a pending batch one call at a time above the box, names a sub-agent's question, and gives back the keyboard", async (t) => {
	const pending = {
		seq: 4,
		calls: [
			{ id: "c1", name: "bash", args: { command: "pwd" } },
			{ id: "c2", name: "write", args: { path: "a.txt", content: "hi" } },
		],
		answers: {},
	}
	const flow = composerFlow({
		answerApproval: (id, answer) => (flow.state.conversation.pendingApproval.answers[id] = answer),
	})
	flow.state.conversation = { pendingApproval: pending }
	// on a phone a card ignores a tap in its first moment: it came up under a finger going
	// elsewhere, or in the place of the call just answered
	t.mock.timers.enable({ apis: ["Date"] })
	layout.phone = true
	t.after(() => (layout.phone = false))
	const { el } = mount(t, Composer, { commands: [], mentions: false }, flow)
	const approve = () => [...el.querySelectorAll("button")].find((button) => button.textContent === "Approve")
	assert.ok(el.textContent.includes("Run this command?"))
	assert.ok(!el.textContent.includes("Write a.txt?"))
	assert.ok(el.textContent.includes("1 of 2"))
	assert.ok(approve().compareDocumentPosition(el.querySelector("fieldset")) & Node.DOCUMENT_POSITION_FOLLOWING)

	approve().click()
	await nextTick()
	assert.deepEqual(pending.answers, {})
	t.mock.timers.tick(400)
	approve().click()
	await nextTick()
	assert.ok(!el.textContent.includes("Run this command?"))
	assert.ok(el.textContent.includes("Write a.txt?"))
	assert.ok(el.textContent.includes("2 of 2"))
	approve().click()
	await nextTick()
	assert.deepEqual(pending.answers, { c1: "Approve" })
	t.mock.timers.tick(400)
	layout.phone = false

	// answering the last call hands the keyboard to the box, not the page
	approve().focus()
	approve().click()
	await nextTick()
	await nextTick()
	assert.equal(approve(), undefined)
	assert.ok(!el.textContent.includes("Write a.txt?"))
	assert.equal(document.activeElement, el.querySelector("textarea"))

	// a sub-agent's question says which sub-agent asks, and leaves when the session's run ends
	const conversation = subagentConversation()
	applyEvent(conversation, {
		type: "approval_required", seq: 6, calls: [{ id: "c2", name: "bash", args: { command: "rm x" } }], subagent_id: "c1",
	})
	applyEvent(conversation, { type: "run_ended", seq: 7, reason: "paused", subagent_id: "c1" })
	const answers = []
	const asked = composerFlow({ answerApproval: (id, answer) => answers.push([id, answer]) })
	asked.state.conversation = conversation
	const child = mount(t, Composer, { commands: [], mentions: false }, asked)
	assert.ok(child.el.textContent.includes("Run this command?"))
	assert.ok(child.el.textContent.includes("Sub-agent: count beans"))
	;[...child.el.querySelectorAll("button")].find((button) => button.textContent === "Approve").click()
	assert.deepEqual(answers, [["c2", "Approve"]])
	applyEvent(conversation, { type: "run_ended", seq: 8, reason: "aborted" })
	await nextTick()
	assert.ok(!child.el.textContent.includes("Run this command?"))
})

test("a reply's suggested replies wait under it: a tap sends one, or ticks several to send together", async (t) => {
	const sent = []
	const conversation = reactive(initialConversation())
	const flow = {
		options: {},
		state: reactive({ sessionId: "s1", loading: false, conversation }),
		send: async (text) => !!sent.push(text),
	}
	let seq = 0
	const reply = (id, args) => {
		for (const event of [
			{ type: "run_started" },
			{ type: "user_message", content: "go" },
			{ type: "assistant_message", content: [{ type: "text", text: "Which?" }, { type: "tool_call", id, name: "suggest_replies", arguments: args }] },
			{ type: "tool_result", tool_call_id: id, name: "suggest_replies", content: "[shown]", details: { multi_select: false, ...args } },
			{ type: "run_ended", reason: "done" },
		])
			applyEvent(conversation, { ...event, seq: ++seq })
	}
	reply("s1", { replies: ["Yes", "No"] })
	const { el } = mount(t, MessageList, {}, flow)
	await nextTick()
	const button = (label, root = el) => [...root.querySelectorAll("button")].find((b) => b.textContent.trim() === label)
	button("Yes").click()
	assert.deepEqual(sent, ["Yes"])

	// a pick-several set sends the ticked answers together, in its order
	reply("s2", { replies: ["CRM", "Helpdesk", "HR"], multi_select: true })
	await nextTick()
	assert.equal(button("Yes"), undefined)
	assert.ok(button("Send").classList.contains("invisible")) // until something is ticked
	for (const label of ["HR", "CRM", "Helpdesk", "Helpdesk"]) button(label).click()
	await nextTick()
	assert.deepEqual(["CRM", "Helpdesk", "HR"].map((label) => button(label).getAttribute("aria-pressed")), ["true", "false", "true"])
	button("Send").click()
	assert.equal(sent.at(-1), "CRM, HR")

	// none while a run goes, where the user can't send, nor once they say something
	conversation.running = true
	await nextTick()
	assert.equal(button("CRM"), undefined)
	conversation.running = false
	await nextTick()
	assert.ok(button("CRM"))
	const readOnly = mount(t, MessageList, { suggestions: false }, flow)
	await nextTick()
	assert.equal(button("CRM", readOnly.el), undefined)
	applyEvent(conversation, { type: "user_message", seq: ++seq, content: "CRM, HR" })
	await nextTick()
	assert.equal(button("CRM"), undefined)
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

test("the thread shows the empty state, a loading line while a chat opens, and a sent message before the server echoes it", async (t) => {
	const conversation = reactive(initialConversation())
	const flow = { options: {}, state: reactive({ sessionId: "s1", loading: false, conversation }) }
	const { el } = mount(t, MessageList, {}, flow)
	const sending = [{ key: "sending:1", entry: { type: "user_message", content: [{ type: "text", text: "count the todos" }], ts: 10 } }]
	// a session without saved messages, as after a reload
	assert.ok(el.textContent.includes("What would you like to build?"))

	flow.state.loading = true
	await nextTick()
	assert.ok(el.textContent.includes("Loading"))
	assert.ok(!el.textContent.includes("What would you like to build?"))

	// a first message in flight keeps its bubble and status while the new session loads
	conversation.sending = sending
	await nextTick()
	assert.ok(!el.textContent.includes("Loading"))
	assert.ok(el.textContent.includes("count the todos"))
	assert.ok(el.textContent.includes("Working"))

	// nothing left once it has loaded: the empty state again
	conversation.sending = []
	flow.state.loading = false
	await nextTick()
	assert.ok(!el.textContent.includes("Loading"))
	assert.ok(el.textContent.includes("What would you like to build?"))

	// the server's copy arrives: the same message, now a real entry
	conversation.sending = sending
	await nextTick()
	applyEvent(conversation, { type: "user_message", seq: 1, content: [{ type: "text", text: "count the todos" }], ts: 11 })
	await nextTick()
	assert.equal(conversation.sending.length, 0)
	assert.equal(el.textContent.match(/count the todos/g).length, 1)
})

test("selecting text in the thread shows Add to chat, which quotes it for the composer, unless the chat is read-only", async (t) => {
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
	const selectRange = (range) => {
		document.getSelection().removeAllRanges()
		document.getSelection().addRange(range)
		t.mock.timers.tick(150) // jsdom's queued selectionchange arms the pill
		t.mock.timers.tick(150) // the debounce
		return nextTick()
	}
	const select = (node) => {
		const range = document.createRange()
		range.selectNodeContents(node)
		return selectRange(range)
	}

	await select(el.querySelector("[data-prompt-key] .whitespace-pre-wrap"))
	assert.equal(pill().textContent.trim(), "Add to chat")
	// centered over the selection, sitting above it
	assert.equal(pill().style.left, "200px")
	assert.equal(pill().style.top, "200px")
	assert.ok(pill().style.transform.includes("-100%"))
	// over several lines the box spans the column: the pill stays over the first line…
	boxes.range = box(0, 200, 800, 268)
	boxes.lines = { "the daemon pins the list": [box(100, 200, 160, 220), box(0, 224, 800, 244), box(0, 248, 240, 268)] }
	document.dispatchEvent(new window.Event("scroll"))
	await nextTick()
	assert.equal(pill().style.left, "130px")
	assert.equal(pill().style.top, "200px")
	// …or goes under the last one when there is no room above
	boxes.range = box(0, 10, 800, 78)
	boxes.lines = { "the daemon pins the list": [box(100, 10, 160, 30), box(0, 34, 800, 54), box(0, 58, 240, 78)] }
	document.dispatchEvent(new window.Event("scroll"))
	await nextTick()
	assert.equal(pill().style.left, "120px")
	assert.equal(pill().style.top, "78px")
	delete boxes.lines

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
	assert.equal(pill().style.top, "564px")

	pill().click()
	await nextTick()
	assert.deepEqual(quotes, ["the daemon pins the list"])
	assert.equal(document.getSelection().rangeCount, 0)
	assert.equal(pill(), null)

	// bold and italic split a line into runs, and a drag from the end of the line above
	// covers whole blocks: either way the pill centers on the first line's selected text
	const block = document.createElement("div")
	block.innerHTML = "<p>Here it is:</p>\n<p><strong>Done</strong> so <em>far</em></p>"
	el.querySelector(".flow-thread").append(block)
	const [intro, line] = block.querySelectorAll("p")
	const far = line.querySelector("em").firstChild
	boxes.range = box(0, 260, 800, 320)
	boxes.lines = {
		"Here it is:": [box(0, 260, 90, 280)],
		Done: [box(100, 300, 140, 320)],
		" so ": [box(140, 300, 170, 320)],
		far: [box(170, 300, 200, 320)],
	}
	for (const [node, offset] of [[line.querySelector("strong").firstChild, 0], [intro.firstChild, "Here it is:".length]]) {
		const range = document.createRange()
		range.setStart(node, offset)
		range.setEnd(far, far.length)
		await selectRange(range)
		assert.equal(pill().style.left, "150px")
		assert.equal(pill().style.top, "300px")
	}
	delete boxes.lines
	block.remove()

	// text outside the thread is not the thread's to quote
	const outside = document.createElement("p")
	outside.textContent = "elsewhere"
	document.body.append(outside)
	t.after(() => outside.remove())
	await select(outside)
	assert.equal(pill(), null)

	// a chat the host reports read-only has no composer to quote into
	t.after(() => document.getSelection().removeAllRanges())
	flow.state.session = { read_only: true }
	await nextTick()
	await select(el.querySelector("[data-prompt-key] .whitespace-pre-wrap"))
	assert.equal(pill(), null)
})

test("a bubble shows the message as written: its quotes, code references and skill commands", async (t) => {
	const { createFlowStore } = await import("../src/store.js")
	const UserBubble = await loadComponent("UserBubble")
	const store = createFlowStore({}, { requireCwd: false, skillsEnabled: false })
	const bubble = (entry) => mount(t, UserBubble, { entry: { type: "user_message", ...entry } }, store).el

	// quotes above its text, a code reference as a chip
	const quoted = bubble({ seq: 1, ts: 10, content: "why?\n\n> pins the list\n> in place\n\n@/w/a.py:3" })
	assert.equal(quoted.querySelector("blockquote").textContent, "pins the list\nin place")
	assert.ok(quoted.textContent.includes("a.py (3)"))
	assert.ok(!quoted.textContent.includes(">"))
	assert.ok(quoted.querySelector(".whitespace-pre-wrap").textContent.endsWith("why?"))

	// a skill the user started keeps its blue command prefix, its body hidden
	const block = (name) => `<skill name="${name}" location="/skills/${name}/SKILL.md">\nbody\n</skill>`
	const started = bubble({ seq: 2, content: `${block("security-review")}\n\ncheck this branch` })
	assert.equal(started.querySelector(".text-ink-blue-6").textContent, "/skill:security-review")
	assert.ok(started.textContent.includes("/skill:security-review check this branch"))
	assert.ok(!started.textContent.includes("body"))

	// skill commands anywhere in a bubble stay blue
	const sent = bubble({ seq: 2, content: `${block("review")}\n\n${block("tests")}\n\ncheck /skill:review then /skill:tests` })
	assert.deepEqual([...sent.querySelectorAll(".text-ink-blue-6")].map((span) => span.textContent), [
		"/skill:review",
		"/skill:tests",
	])
	// a bubble still sending has no expansion yet, so the catalog decides
	store.state.skills = [{ name: "review", description: "" }]
	const sending = bubble({ content: "please /skill:review /skill:nope" })
	assert.deepEqual([...sending.querySelectorAll(".text-ink-blue-6")].map((span) => span.textContent), ["/skill:review"])
})

test("a new chat shows its folder, branch and preset over the box until its first message goes out; a sent message leaves the box at once, which takes the next one; a failed send comes back ahead of it", async (t) => {
	let finishSend
	let sent
	let picks = 0
	let creates = 0
	const flow = composerFlow({
		send(message, attachments) {
			sent = { message, attachments }
			return new Promise((resolve) => (finishSend = resolve))
		},
		gitBranch: async () => ({ branch: "work", worktree: true }),
		pickFolder: async () => void picks++,
		folderName: (path) => ({ "/w/expenses": "Expenses app" })[path],
		activePreset: () => flow.state.presets.find((p) => p.id === flow.state.prefs.activePreset) ?? null,
		setActivePreset: (id) => (flow.state.prefs.activePreset = id),
		createPreset: () => creates++,
	})
	Object.assign(flow.state, {
		sessionId: null,
		prefs: { mode: "ask", cwd: "/w/expenses", activePreset: null },
		presets: [{ id: "r1", name: "Reviewer", tools: [] }],
		conversation: { running: false, sending: [] },
	})
	const { el, vm } = mount(t, Composer, { commands: [], mentions: false, imagesOnly: false }, flow)
	const box = el.querySelector("textarea")
	const sendButton = () => el.querySelector("button[title='Send']")
	const folder = () => el.querySelector("button[title='Change working directory']")
	await new Promise((resolve) => setImmediate(resolve))
	assert.equal(folder().textContent.trim(), "Expenses app") // its workspace's name
	// the branch, marked as a linked worktree's
	const branch = [...el.querySelector("[title='Branch']").children].map((child) => child.textContent.trim())
	assert.deepEqual(branch.filter(Boolean), ["work", "worktree"])
	folder().click()
	assert.equal(picks, 1)

	// the preset: Standard, or one picked from its own list, found by its search; a search that
	// finds none leads to a new one
	const preset = () => el.querySelector("button[title='Agent preset']")
	const rows = () => [...preset().parentElement.querySelectorAll("[data-palette-item]")].map((row) => [row.textContent.trim(), row.getAttribute("aria-current")])
	const row = (name) => [...preset().parentElement.querySelectorAll("[data-palette-item]")].find((r) => r.textContent.trim() === name)
	const search = async (text) => {
		const field = preset().parentElement.querySelector("input")
		field.value = text
		field.dispatchEvent(new window.Event("input"))
		await nextTick()
	}
	assert.equal(preset().textContent.trim(), "Standard")
	preset().click()
	await nextTick()
	await nextTick()
	assert.equal(document.activeElement.placeholder, "Search presets…")
	assert.deepEqual(rows(), [["Standard", "true"], ["Reviewer", null]])
	await search("rev")
	assert.deepEqual(rows(), [["Reviewer", null]])
	await search("rev x")
	assert.deepEqual(rows(), [["Create a preset", null]])
	assert.match(preset().parentElement.textContent, /No matching presets/)
	await search("")
	row("Reviewer").click()
	await nextTick()
	assert.equal(flow.state.prefs.activePreset, "r1")
	assert.equal(preset().textContent.trim(), "Reviewer")
	assert.deepEqual(rows(), [])
	preset().click()
	await nextTick()
	assert.equal(preset().parentElement.querySelector("input").value, "")
	assert.deepEqual(rows(), [["Standard", null], ["Reviewer", "true"]])
	await search("zzz")
	row("Create a preset").click()
	await nextTick()
	assert.equal(creates, 1)
	assert.deepEqual(rows(), [])

	// gone once the first message is out, and from the chat it starts
	flow.state.conversation.sending = [{ key: "sending:1" }]
	await nextTick()
	assert.equal(folder(), null)
	flow.state.sessionId = "s1"
	flow.state.conversation.sending = []
	await nextTick()
	assert.equal(folder(), null)
	vm.prefill("Review this")
	const input = el.querySelector("input[type=file]")
	Object.defineProperty(input, "files", {
		configurable: true,
		value: [new dom.window.File(["document"], "notes.pdf", { type: "application/pdf" })],
	})
	input.dispatchEvent(new dom.window.Event("change", { bubbles: true }))
	await nextTick()
	assert.ok(el.textContent.includes("notes.pdf"))

	sendButton().focus()
	sendButton().click()
	await nextTick()
	await nextTick()
	// the message is already a bubble in the thread: its attachment leaves the box with the text
	assert.equal(box.value, "")
	assert.ok(!el.textContent.includes("notes.pdf"))
	assert.equal(el.querySelector('[role="status"]'), null)
	assert.equal(sendButton().disabled, true)
	assert.equal(sendButton().getAttribute("aria-busy"), "true")
	assert.ok(sendButton().querySelector(".animate-spin"))
	assert.equal(sent.message, "Review this")
	assert.equal(sent.attachments[0].name, "notes.pdf")
	// while it is out, the box takes the next one
	assert.equal(box.disabled, false)
	assert.equal(document.activeElement, box)
	assert.equal(el.querySelector("button[title='Attach files']").disabled, false)

	// a send that fails hands the draft back
	finishSend(false)
	await new Promise((resolve) => setImmediate(resolve))
	assert.equal(box.value, "Review this")
	assert.ok(el.textContent.includes("notes.pdf"))
	assert.equal(sendButton().disabled, false)
	assert.equal(el.querySelector(".animate-spin"), null)

	// ahead of what was typed while it was out
	sendButton().click()
	await nextTick()
	box.value = "second"
	box.dispatchEvent(new window.Event("input"))
	finishSend(false)
	await new Promise((resolve) => setImmediate(resolve))
	assert.equal(box.value, "Review this\n\nsecond")

	// one that lands spins until it has, even once the run starts, then leaves the box empty
	sendButton().click()
	await nextTick()
	flow.state.conversation.running = true
	await nextTick()
	assert.ok(el.querySelector("button[title='Send'] .animate-spin"))
	finishSend(true)
	await new Promise((resolve) => setImmediate(resolve))
	assert.equal(box.value, "")
	assert.ok(!el.textContent.includes("notes.pdf"))
	assert.equal(el.querySelector(".animate-spin"), null)
	assert.ok(el.querySelector("button[title='Stop']"))
})

test("a file attached while a message is out stays with the chat it creates; a switch or closing the composer discards it", async (t) => {
	const discarded = []
	let prepared = 0
	const flow = composerFlow({
		send: () => new Promise(() => {}),
		prepareAttachment: async (file) => ({ id: `F${++prepared}`, name: file.name, kind: "file" }),
		discardAttachments: async (ids) => discarded.push(...ids),
	})
	flow.state.sessionId = null
	flow.state.conversation = { running: false, sending: [] }
	const view = reactive({ open: true })
	const host = { render: () => (view.open ? h(Composer, { ref: "composer", commands: [], mentions: false, imagesOnly: false }) : null) }
	const { el, vm } = mount(t, host, {}, flow)
	vm.$refs.composer.prefill("first")
	await nextTick()
	el.querySelector("button[title='Send']").click()
	await nextTick()
	const input = el.querySelector("input[type=file]")
	Object.defineProperty(input, "files", { value: [new window.File(["document"], "notes.pdf", { type: "application/pdf" })] })
	const attach = () => {
		input.dispatchEvent(new window.Event("change"))
		return new Promise((resolve) => setImmediate(resolve))
	}
	await attach()

	// the store opens the chat the message created with the message still on its way
	flow.state.conversation = { running: false, sending: [{ key: "sending:1" }] }
	flow.state.sessionId = "new"
	await nextTick()
	assert.ok(el.textContent.includes("notes.pdf"))
	assert.deepEqual(discarded, [])

	flow.state.conversation = { running: false, sending: [] }
	flow.state.sessionId = "other"
	await nextTick()
	assert.ok(!el.textContent.includes("notes.pdf"))
	assert.deepEqual(discarded, ["F1"])

	// the message still out, the composer goes away
	await attach()
	view.open = false
	await nextTick()
	assert.deepEqual(discarded, ["F1", "F2"])
})

test("quotes and code references stage as chips, go out under the message, and come back with a rewound draft", async (t) => {
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
		addCodeRef(path, start, end) { this.state.codeRefs.push({ path, rel: path, start, end }) },
		addQuote(text) { this.state.quotes.push(text) },
		clearCodeRefs(went) { this.state.codeRefs = went ? this.state.codeRefs.filter((ref) => !went.includes(ref)) : [] },
		clearQuotes(went) { this.state.quotes = went ? this.state.quotes.filter((quote) => !went.includes(quote)) : [] },
		removeQuote(i) { this.state.quotes.splice(i, 1) },
		setDraft(draft) { this.state.draft = draft },
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

	// a rewound message brings its quotes and code references back as chips, in place of the staged ones
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
			quotes: [], queued: [], skills: [], conversation: { running: false, sending: [] }, draft: null,
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

test("a send waits for its attachment's preparation, which can fail and be retried", async (t) => {
	const { el, flow, requests, sent, discarded } = preparingComposer(t)
	await nextTick()
	assert.equal(requests.length, 1)
	assert.equal(requests[0].model, "GPT")
	assert.equal(flow.state.sessionId, null)
	assert.equal(el.querySelector('[role="status"]').getAttribute("aria-label"), "Preparing notes.pdf")
	requests[0].reject(new Error("Upload failed"))
	await new Promise((resolve) => setImmediate(resolve))
	assert.ok(el.textContent.includes("Upload failed"))
	el.querySelector("button[title='Send']").click()
	await nextTick()
	assert.equal(sent.length, 0)
	assert.equal(el.querySelector("textarea").value, "Read this")

	el.querySelector("button[aria-label='Retry notes.pdf']").click()
	await nextTick()
	el.querySelector("button[title='Send']").click()
	await nextTick()
	assert.equal(sent.length, 0)
	assert.equal(el.querySelector("textarea").value, "Read this")
	assert.ok(el.querySelector("textarea").disabled) // it still holds the message going out
	assert.ok(el.querySelector("button[title='Send'] .animate-spin"))
	requests[1].resolve({ id: "F2", name: "notes.pdf", kind: "file" })
	await new Promise((resolve) => setImmediate(resolve))
	assert.deepEqual(sent, [{ text: "Read this", ids: ["F2"] }])
	assert.equal(requests.length, 2)
	assert.equal(el.querySelector("textarea").value, "")
	assert.deepEqual(discarded, [])
})

test("a file removed, or left behind by a chat switch, while it is prepared is discarded and never sent", async (t) => {
	const { el, flow, requests, sent, discarded } = preparingComposer(t)
	await nextTick()
	el.querySelector("button[aria-label='Remove notes.pdf']").click()
	requests[0].resolve({ id: "F1", name: "notes.pdf", kind: "file" })
	await new Promise((resolve) => setImmediate(resolve))
	assert.deepEqual(discarded, ["F1"])
	assert.equal(sent.length, 0)
	assert.ok(!el.textContent.includes("notes.pdf"))

	// attached again and sent, then the chat switches before the file is ready
	el.querySelector("input[type=file]").dispatchEvent(new dom.window.Event("change", { bubbles: true }))
	await nextTick()
	el.querySelector("button[title='Send']").click()
	flow.state.sessionId = "other"
	await nextTick()
	requests[1].resolve({ id: "F2", name: "notes.pdf", kind: "file" })
	await new Promise((resolve) => setImmediate(resolve))
	assert.equal(sent.length, 0)
	assert.equal(el.querySelector("textarea").value, "Read this")
	assert.ok(!el.textContent.includes("notes.pdf")) // a switch drops staged files, send or not
})

test("the settings shell renders a host's tabs and panels, as a page in a narrow frame", async (t) => {
	const groups = [{ label: "Settings", tabs: [{ id: "alpha", label: "Alpha", icon: "x" }, { id: "beta", label: "Beta", icon: "y" }] }]
	const flow = { state: reactive({ settingsOpen: true }), setSettingsOpen() {} }
	const { el, unmount } = mount(t, {
		render: () => h(SettingsDialog, { groups }, {
			alpha: () => h("p", { "data-test": "alpha" }, "A"),
			beta: () => h("p", { "data-test": "beta" }, "B"),
		}),
	}, {}, flow)
	assert.deepEqual([...el.querySelectorAll("[data-stub=SettingsNavItem]")].map((b) => b.textContent.trim()), ["Alpha", "Beta"])
	assert.deepEqual([...el.querySelectorAll("[data-stub=SettingsPanel]")].map((p) => `${p.dataset.value}:${p.textContent.trim()}`), ["alpha:A", "beta:B"])
	unmount() // the page below has the browser's history to itself

	// a narrow frame shows them as a page: a list whose rows open their panel, a way back, a close
	layout.narrow = layout.phone = true
	t.after(() => (layout.narrow = layout.phone = false))
	const narrow = { state: reactive({ settingsOpen: false }), setSettingsOpen: (open) => (narrow.state.settingsOpen = open) }
	const beta = reactive({ form: false, dirty: false }) // a sub-page in beta's panel, like a record's form
	const { el: host } = mount(t, {
		render: () => h(SettingsDialog, { groups }, {
			alpha: () => h("p", { "data-test": "alpha" }, "A"),
			beta: () => beta.form
				? h(SettingsPage, {
					title: "Edit beta",
					back: "Back to beta",
					onBack: () => (beta.dirty ? (dialogStack.value = [{ id: 1 }]) : (beta.form = false)),
				})
				: h("p", { "data-test": "beta" }, "B"),
		}),
	}, {}, narrow)
	// the page slides in and out: a move waits for its frames
	const slid = () => new Promise((resolve) => setTimeout(resolve, 20))
	// a phone's back goes back a screen: each page and dialog is an entry in the browser's history, added after a tap
	const entries = () => window.history.state?.flowSettings ?? 0
	const phoneBack = () => (window.history.back(), slid())
	const tap = () => document.body.click()
	tap()
	narrow.state.settingsOpen = true
	await slid()
	const page = () => host.querySelector("[role=dialog]")
	const rows = () => [...page().querySelectorAll("nav button")].map((row) => row.textContent.trim())
	assert.deepEqual([rows(), entries()], [["Alpha", "Beta"], 1])
	page().querySelectorAll("nav button")[1].click()
	await slid()
	assert.deepEqual([rows(), page().querySelector("[data-test=beta]")?.textContent, entries()], [[], "B", 2])
	// the sub-page's way back is the header's, to its section, and not a second button of its own
	beta.form = true
	await nextTick()
	const head = () => page().querySelector("header button")
	assert.deepEqual([head().textContent.trim(), page().querySelector("button[title='Back to beta']"), entries()], ["Beta", null, 3])
	// a phone turned mid-edit keeps the page until settings closes: the form stays mounted, its way back the header's
	const form = page().querySelector("h2")
	layout.narrow = layout.phone = false
	await nextTick()
	assert.deepEqual([page()?.querySelector("h2") === form, page()?.querySelector("button[title='Back to beta']")], [true, null])
	layout.narrow = layout.phone = true
	await nextTick()
	head().click()
	await slid()
	assert.deepEqual([beta.form, head().textContent.trim(), entries()], [false, "Settings", 2])
	// a form with changes asks first, and the back closes the ask: an ask a tap opened is an entry of its own
	tap()
	beta.form = beta.dirty = true
	await nextTick()
	head().click()
	await nextTick()
	assert.deepEqual([beta.form, dialogStack.value.length, entries()], [true, 1, 4])
	await phoneBack()
	assert.deepEqual([beta.form, dialogStack.value.length, entries()], [true, 0, 3])
	// one the back opens can't be (no tap since), so the form is short of its entry until the next tap
	await phoneBack()
	assert.deepEqual([beta.form, dialogStack.value.length, entries()], [true, 1, 2])
	await phoneBack()
	assert.deepEqual([beta.form, dialogStack.value.length, entries()], [true, 0, 1])
	tap()
	await nextTick()
	assert.equal(entries(), 3)
	beta.dirty = false
	await phoneBack()
	assert.deepEqual([beta.form, head().textContent.trim(), entries()], [false, "Settings", 2])
	;[...page().querySelectorAll("button")].find((button) => button.textContent.trim() === "Settings").click()
	await slid()
	assert.deepEqual([rows(), page().querySelector("[data-test=beta]"), entries()], [["Alpha", "Beta"], null, 1])
	await phoneBack()
	assert.deepEqual([narrow.state.settingsOpen, entries()], [false, 0])
	// the close leaves every page's entry
	tap()
	narrow.state.settingsOpen = true
	await slid()
	page().querySelectorAll("nav button")[1].click()
	await slid()
	page().querySelector("button[title=Close]").click()
	await slid()
	assert.deepEqual([narrow.state.settingsOpen, entries()], [false, 0])
	// settings opened before the frame was a phone's keeps its dialog until it closes: one entry, whatever
	// section the page last showed, so one back closes it
	layout.narrow = layout.phone = false
	tap()
	narrow.state.settingsOpen = true
	await slid()
	assert.equal(entries(), 0)
	layout.narrow = layout.phone = true
	await nextTick()
	assert.deepEqual([page(), !!host.querySelector("[data-stub=SettingsDialog]"), entries()], [null, true, 1])
	await phoneBack()
	assert.deepEqual([narrow.state.settingsOpen, entries()], [false, 0])
})

test("a settings page takes a way back and actions beside its heading, or after its body when narrow", (t) => {
	let backs = 0
	const page = () => mount(t, {
		render: () => h(SettingsPage, { title: "Edit agent", back: "Back to agents", onBack: () => backs++ }, {
			actions: () => h("button", { "data-test": "toggle" }, "Enabled"),
			default: () => h("p", "fields"),
			footer: () => h("button", { "data-test": "save" }, "Save"),
		}),
	}, {}, {}).el
	const el = page()
	assert.equal(el.querySelector("h2").textContent, "Edit agent")
	assert.equal(el.textContent, "Edit agentEnabledfieldsSave")
	assert.ok(el.querySelector(".border-t [data-test=save]"), "the footer sits outside the scrolling body")
	el.querySelector("button[title='Back to agents']").click()
	assert.equal(backs, 1)
	const bare = mount(t, SettingsPage, { title: "General" }, {})
	assert.equal(bare.el.querySelector(".flow-icon-btn"), null)
	assert.equal(bare.el.querySelector(".border-t"), null)
	layout.narrow = true
	t.after(() => (layout.narrow = false))
	assert.equal(page().textContent, "Edit agentfieldsEnabledSave")
})

test("rewind is offered on a logged message of a chat that can rewind, and nowhere else", async (t) => {
	const { createFlowStore } = await import("../src/store.js")
	const UserBubble = await loadComponent("UserBubble")
	const rewind = (store, entry) =>
		mount(t, UserBubble, { entry: { type: "user_message", content: "hello", ...entry } }, store).el.querySelector(
			'button[title="Rewind to this message"]',
		)
	// the host client's capability decides, for the bubbles and the composer's /rewind
	for (const supported of [false, true]) {
		const client = supported ? { rewind() {} } : {}
		const store = createFlowStore(client, { requireCwd: false, skillsEnabled: false })
		assert.equal(!!rewind(store, { seq: 2 }), supported)
		const composer = mount(t, Composer, { mentions: false }, store)
		composer.vm.prefill("/rewind")
		await nextTick()
		assert.equal(composer.el.textContent.includes("Branch from before your last message"), supported)
	}

	const store = createFlowStore({ rewind() {} }, { requireCwd: false, skillsEnabled: false })
	// not a message steered into a running turn, though the run's own message has one
	store.state.conversation.steeredSeqs = [4]
	assert.equal(rewind(store, { seq: 4 }), null)
	assert.ok(rewind(store, { seq: 2 }))
	// not a message still on its way
	assert.equal(rewind(store, {}), null)
	// not in a chat the host reports read-only
	store.state.session = { read_only: true }
	assert.equal(rewind(store, { seq: 2 }), null)
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

test("open thoughts and tool rows stay open and unfolded as the run ends, until the turn is folded; a click focuses nothing", async (t) => {
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

	// the thought merges into a tool group
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
	await nextTick()
	rowButton(el, "ls").click()
	await nextTick()
	assert.ok(el.querySelector("pre"))

	applyEvent(conversation, { type: "assistant_message", seq: 5, ts: 13, content: [{ type: "text", text: "One file." }], stop_reason: "stop" })
	applyEvent(conversation, { type: "run_ended", seq: 6, ts: 13, reason: "done" })
	await nextTick()
	const fold = el.querySelector("[data-turn-fold] button")
	assert.equal(fold.getAttribute("aria-expanded"), "true")
	assert.ok(panel())
	assert.ok(el.querySelector("pre"))

	// folding it by hand closes the rows with it
	fold.click()
	await nextTick()
	assert.equal(fold.getAttribute("aria-expanded"), "false")
	assert.equal(el.querySelector("pre"), null)

	// a click doesn't focus the thread's buttons, links or summaries, so a closing dialog can't scroll back to one:
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

test("a view on the bottom stays there when a panel or the window resizes the list, unless an opened row pushed it off", async (t) => {
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
	// jsdom has no layout: the list's scroll geometry is faked (scrollTop clamps like a
	// browser's) and resizes are reported by hand
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

	// a row opened below the view, then a panel opening, leaves the view where it is
	box.height = 2400
	resize(thread)
	box.height = 2480
	resize(list, thread)
	assert.equal(list.scrollTop, 2245 - 816)
})

test("a saved preset stays open as saved: a new one becomes an edit of itself, the Standard one locks the core tools, a chat marks the one it was made with, and the composer's \"Create a preset\" opens a blank one", async (t) => {
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
	el.querySelector("button[title='Back to presets']").click()
	await nextTick()

	assert.match(el.textContent, /Core tools and the built-in prompt/) // no list yet: nothing to count
	await store.refreshTools()
	await nextTick()
	assert.match(el.textContent, /2 of 3 tools/) // the Standard row: core and extensions on, bundled off

	el.querySelector("button[title='Edit preset']").click() // the Standard row comes first
	await nextTick()
	assert.equal(el.querySelector("h2").textContent, "Standard preset")
	assert.equal(el.querySelector("input[type=text]"), null, "no name to edit")
	assert.equal(el.querySelector("textarea"), null, "no prompt to edit")
	const boxes = [...el.querySelectorAll("input[type=checkbox]")]
	assert.deepEqual(boxes.map((box) => [box.checked, box.disabled]), [[true, true], [false, false], [true, false]])
	assert.ok(button("Save").disabled)

	boxes[1].click()
	await nextTick()
	assert.ok(!button("Save").disabled)
	button("Save").click()
	await nextTick()
	assert.deepEqual(store.state.prefs.defaultPreset, { tools: ["grep"], extensionTools: ["hello"] })
	assert.equal(el.querySelector("h2").textContent, "Standard preset") // the form stays open
	assert.ok(button("Save").disabled)
	el.querySelector("button[title='Back to presets']").click()
	await nextTick()
	assert.match(el.textContent, /3 of 3 tools/)

	// inside a chat, the list marks the preset the chat records
	const marked = () => [...el.querySelectorAll(".bg-surface-gray-1 .font-medium")].map((name) => name.textContent)
	assert.deepEqual(marked(), ["Standard"])
	store.state.sessionId = "s1"
	store.state.session = { config: { preset: store.state.presets[0].id } }
	await nextTick()
	assert.deepEqual(marked(), ["Reviewer"])

	// settings opens on this tab, on a blank preset; the next opening is the list again
	store.createPreset()
	assert.deepEqual([store.state.settingsOpen, store.state.settingsTab], [true, "presets"])
	assert.equal(mount(t, SettingsPresets, {}, store).el.querySelector("h2").textContent, "New preset")
	assert.equal(mount(t, SettingsPresets, {}, store).el.querySelector("h2").textContent, "Agent presets")
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

test("a sub-agent's row opens its tab and shows its state, or keeps its dropdown for a host without a workspace panel", async (t) => {
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

	// a host without a workspace panel keeps the row's dropdown
	const done = subagentConversation()
	applyEvent(done, { type: "assistant_message", seq: 6, ts: 12, content: [{ type: "text", text: "forty-two" }], subagent_id: "c1" })
	applyEvent(done, { type: "run_ended", seq: 7, ts: 12, reason: "done", subagent_id: "c1" })
	applyEvent(done, {
		type: "tool_result", seq: 8, ts: 12, tool_call_id: "c1", name: "subagent",
		content: "forty-two\n\n[subagent_id: c1]", details: { subagent_id: "c1", agent: "general", end_reason: "done" },
	})
	const bare = mount(t, MessageList, {}, {
		options: { workspace: false },
		state: reactive({ sessionId: "s1", loading: false, conversation: done }),
		openSubagent: (id) => opened.push(id),
	})
	await nextTick()
	rowButton(bare.el, "count beans").click()
	await nextTick()
	assert.deepEqual(opened, ["c1"])
	assert.ok(bare.el.querySelector("pre").textContent.includes("forty-two"))
})

test("a sub-agent's tab says it is loading with its session, starting until it runs, then draws its thread with the session's rows", async (t) => {
	const conversation = subagentConversation()
	const flow = { options: {}, capabilities: { rewind: true }, state: reactive({ sessionId: "s1", loading: true, conversation }) }
	const { el } = mount(t, SubagentView, { id: "c9" }, flow)
	assert.ok(el.textContent.includes("Loading"))
	assert.ok(!el.textContent.includes("Starting"))
	flow.state.loading = false
	await nextTick()
	assert.ok(!el.textContent.includes("Loading"))
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

test("the workspace panel is inert while closed, slides only as it opens or shuts, draws a sub-agent's tab itself, takes the host's menu, view and empty state, and fills a narrow frame", async (t) => {
	const conversation = subagentConversation()
	const workspace = reactive({
		open: false, maximized: false, view: null, active: "c1",
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
	t.mock.timers.enable({ apis: ["setTimeout"] })
	const { el } = mount(t, panel, {}, flow)
	await nextTick()
	// closed, its hidden buttons can't take focus
	const aside = el.querySelector("aside")
	assert.ok(aside.hasAttribute("inert"))
	// it slides as it opens, and only then: a frame crossing the narrow width moves it at once
	const sliding = () => aside.className.includes("transition-")
	assert.ok(!sliding())
	workspace.open = true
	await nextTick()
	assert.ok(!aside.hasAttribute("inert"))
	assert.ok(sliding())
	t.mock.timers.tick(250)
	await nextTick()
	assert.ok(!sliding())

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

	// a narrow frame's panel fills it already: no full screen, only the close
	assert.ok(el.querySelector("button[title='Full screen']"))
	layout.narrow = true
	t.after(() => (layout.narrow = false))
	await nextTick()
	assert.deepEqual([el.querySelector("button[title='Full screen']"), !!el.querySelector("button[title='Close panel']")], [null, true])
	assert.ok(!sliding())
})

const settle = () => new Promise((resolve) => setImmediate(resolve))

// monaco can't run under jsdom: a fake of what the editor view calls, keeping its
// models by uri like monaco does (one per uri, gone once disposed)
const monacoModels = new Map()
let anonymousModels = 0
function fakeEditor() {
	let model = null
	return {
		addCommand() {},
		onDidChangeCursorSelection() {},
		addContentWidget() {},
		getModel: () => model,
		setModel: (next) => (model = next),
		updateOptions() {},
		dispose() {},
	}
}
globalThis.monaco = {
	KeyMod: { CtrlCmd: 2048 },
	KeyCode: { KeyS: 49 },
	Uri: { file: (path) => `file://${path}` },
	editor: {
		create: fakeEditor,
		createDiffEditor: () => ({ ...fakeEditor(), getModifiedEditor: fakeEditor }),
		createModel(value, language, uri = `inmemory://${++anonymousModels}`) {
			assert.ok(!monacoModels.has(uri), `a second model for ${uri}`)
			let version = 1
			const listeners = []
			const model = {
				getValue: () => value,
				// typing and a refetch both land here
				setValue(text) {
					value = text
					version++
					for (const listener of listeners) listener()
				},
				getAlternativeVersionId: () => version,
				getLanguageId: () => language ?? "plaintext",
				onDidChangeContent: (listener) => listeners.push(listener),
				dispose: () => monacoModels.delete(uri),
			}
			monacoModels.set(uri, model)
			return model
		},
		defineTheme() {},
		setTheme() {},
	},
}

// the harness app's panel and file view on the real store, browsing /proj
async function editorPanel(t, client = {}) {
	const { createFlowStore } = await import("../src/store.js")
	globalThis.localStorage = { getItem: () => null, setItem() {} }
	globalThis.MutationObserver = window.MutationObserver
	globalThis.getComputedStyle = (el) => window.getComputedStyle(el)
	const daemon = { readFile: async (cwd, path) => ({ path, content: "v0" }), ...client }
	const store = createFlowStore(daemon, { requireCwd: false, skillsEnabled: false })
	store.setCwd("/proj")
	const panel = { render: () => h(WorkspacePanel, null, { view: () => h(EditorView) }) }
	const { el } = mount(t, panel, {}, store)
	// after the unmount: an editor still loading then finds no element and stops
	t.after(() => {
		delete globalThis.localStorage
		delete globalThis.MutationObserver
		delete globalThis.getComputedStyle
	})
	return { el, store }
}

test("an open file keeps unsaved edits through a save in flight, a sub-agent's tab and a closed panel, and frees its model once closed", async (t) => {
	const writes = []
	let finish
	const { el, store } = await editorPanel(t, {
		writeFsFile(cwd, path, content) {
			writes.push(content)
			return new Promise((resolve) => (finish = () => resolve({ path })))
		},
	})
	await store.openFile("/proj/a.txt")
	await settle()
	const model = (path) => monacoModels.get(`file://${path}`)
	const tab = store.state.workspace.tabs[0]
	// keys typed while a save is in flight stay, and the tab stays unsaved
	const save = () => el.querySelector("[title='Save (⌘S)']").click()
	model("/proj/a.txt").setValue("v0A")
	await nextTick()
	save()
	model("/proj/a.txt").setValue("v0AB") // typed before the write returns
	finish()
	await settle()
	assert.equal(model("/proj/a.txt").getValue(), "v0AB")
	assert.equal(tab.content, "v0A")
	assert.equal(tab.dirty, true)

	save() // nothing typed this time: the tab ends clean
	finish()
	await settle()
	assert.deepEqual(writes, ["v0A", "v0AB"])
	assert.equal(tab.content, "v0AB")
	assert.equal(tab.dirty, false)

	// unsaved edits outlive a sub-agent's tab and a panel closed from the Files view
	model("/proj/a.txt").setValue("v0AB edited")
	assert.equal(tab.dirty, true)
	store.openSubagent("c1")
	await settle()
	assert.ok(el.textContent.includes("Starting…")) // the sub-agent's tab is the one showing
	store.selectFile("/proj/a.txt")
	await settle()
	assert.equal(model("/proj/a.txt").getValue(), "v0AB edited")

	store.showFilesView()
	store.setWorkspaceOpen(false)
	await settle()
	store.setWorkspaceOpen(true)
	await settle()
	assert.equal(store.state.workspace.active, "/proj/a.txt")
	assert.equal(model("/proj/a.txt").getValue(), "v0AB edited")
	assert.equal(tab.dirty, true)

	// a tab closed behind a sub-agent's, or a chat left, still frees its model
	await store.openFile("/proj/b.txt")
	await settle()
	model("/proj/b.txt").setValue("v0 too")
	store.selectFile("c1")
	store.closeFile("/proj/b.txt")
	await settle()
	assert.equal(model("/proj/b.txt"), undefined)
	store.startNewChat()
	await settle()
	assert.equal(model("/proj/a.txt"), undefined)
})

test("the changed-files list stops polling once the panel closes", async (t) => {
	t.mock.timers.enable({ apis: ["setTimeout"] })
	let polls = 0
	const { el, store } = await editorPanel(t, {
		gitFileDiff: async (cwd, path) => ({ path, original: "old", modified: "new" }),
		gitChanges: async () => (polls++, { root: "/proj", files: [] }),
	})
	await store.openDiffFile("/proj/a.txt")
	await settle()
	el.querySelector("[title='Show files']").click()
	await settle()
	t.mock.timers.tick(3000)
	await settle()
	assert.equal(polls, 2)

	store.setWorkspaceOpen(false)
	await settle()
	for (let i = 0; i < 3; i++) {
		t.mock.timers.tick(3000)
		await settle()
	}
	assert.equal(polls, 2)
})

test("the files bar opens for a chat restored to its Files view, and only another chat's workspace closes it", async (t) => {
	const { el, store } = await editorPanel(t)
	await store.openFile("/proj/a.txt")
	await settle()
	const barOpen = () => el.querySelector("[title='Hide files']") !== null
	const workspace = (fields) => ({ open: false, maximized: false, tabs: [], active: null, view: null, ...fields })
	// the bar's search takes the caret two timeouts on, after a menu's own
	const searchFocused = async () => {
		await new Promise((resolve) => setTimeout(() => setTimeout(resolve)))
		return document.activeElement === el.querySelector("input[placeholder='Search files']")
	}
	assert.equal(barOpen(), false)

	// a chat switch, as the store does it: a fresh workspace, then the next chat's restored one
	store.state.workspace = workspace()
	store.state.sessionId = "s2"
	store.state.session = { config: { cwd: "/proj" } }
	store.state.workspace = workspace({ open: true, view: "files" })
	await nextTick()
	assert.equal(barOpen(), true)
	assert.equal(await searchFocused(), false) // a restored view leaves the caret where it was

	// a new chat's first send opens the chat on the workspace it was browsing
	store.startNewChat()
	await nextTick()
	store.showFilesView()
	await nextTick()
	assert.equal(await searchFocused(), true) // opened by hand, its search has the caret
	await store.openFile("/proj/c.txt") // picked from the bar, which stays open
	await settle()
	assert.equal(barOpen(), true)
	store.state.sessionId = "s3"
	store.state.session = { config: { cwd: "/proj" } }
	await nextTick()
	assert.equal(barOpen(), true)

	const tab = { kind: "editor", path: "/proj/b.txt", name: "b.txt", content: "b", original: null, error: null, loading: false, dirty: false, diff: false }
	store.state.workspace = workspace({ open: true, tabs: [tab], active: tab.path })
	store.state.sessionId = "s4"
	await nextTick()
	assert.equal(barOpen(), false)
})

test("each sub-agent's tab keeps its own place in its thread", async (t) => {
	const conversation = subagentConversation()
	applyEvent(conversation, {
		type: "assistant_message",
		seq: 6,
		ts: 12,
		content: [{ type: "tool_call", id: "c2", name: "subagent", arguments: { task: "weigh", description: "weigh beans" } }],
	})
	applyEvent(conversation, { type: "run_started", seq: 7, ts: 12, subagent_id: "c2" })
	applyEvent(conversation, { type: "user_message", seq: 8, ts: 12, content: "weigh", subagent_id: "c2" })
	const workspace = reactive({
		open: true, maximized: false, view: null, active: "c1",
		tabs: [{ kind: "subagent", path: "c1", name: "Sub-agent: count" }, { kind: "subagent", path: "c2", name: "Sub-agent: weigh" }],
	})
	const flow = { options: {}, state: reactive({ sessionId: "s1", loading: false, conversation, workspace, prefs: {} }) }
	const { el } = mount(t, WorkspacePanel, {}, flow)
	await nextTick()
	const list = el.querySelector(".flow-thread").parentElement
	let top = 1500
	Object.defineProperty(list, "clientHeight", { get: () => 500 })
	Object.defineProperty(list, "scrollHeight", { get: () => 2000 })
	Object.defineProperty(list, "scrollTop", { get: () => top, set: (value) => (top = value) })
	list.dispatchEvent(new window.Event("scroll"))
	list.scrollTop = 300 // read up the first thread
	list.dispatchEvent(new window.Event("scroll"))
	await nextTick()
	assert.ok(el.querySelector("button[title='Scroll to bottom']"))

	workspace.active = "c2"
	await nextTick()
	assert.ok(el.textContent.includes("weigh"))
	assert.equal(el.querySelector("button[title='Scroll to bottom']"), null) // follows its own live end
	assert.notEqual(el.querySelector(".flow-thread").parentElement, list)
})

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
	const results = {
		o: ["src/a/one.js", "src/two.js", "top.js"],
		on: ["src/a/one.js", "src/one.md"],
		a: ["src/a/", "src/a/a.js"],
	}
	const flow = {
		state: reactive({ workspace: { tabs: [], active: null }, prefs: {} }),
		explorerCwd: () => "/w",
		listFiles: async (path) => ({ path: path || "/w", entries: path ? [{ name: "a.js", type: "file" }, { name: "one.js", type: "file" }] : [] }),
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

	// a folder found by its name starts shut, then opens onto all it holds
	await search("a")
	assert.deepEqual(rows(), ["src", "a"])
	assert.equal(row("src/a").getAttribute("aria-expanded"), "false")
	await toggle("src/a")
	await settle()
	assert.deepEqual(rows(), ["src", "a", "a.js", "one.js"])
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

test("the chat list groups chats by their folder, and says it is loading, not that there are no chats or matches", async (t) => {
	t.mock.timers.enable({ apis: ["setTimeout"] })
	const opened = [] // what the rows' buttons asked for
	const flow = {
		options: {},
		state: reactive({
			sessions: [],
			sessionsLoading: true,
			sessionsMore: false,
			sessionId: null,
			prefs: { openFolders: [] },
		}),
		startNewChat({ cwd }) {
			opened.push(`new chat in ${cwd}`)
		},
		openSession(sid) {
			opened.push(sid)
		},
		sessionTitle: (session) => session.title,
		folderName: (path) => path.split("/").pop(),
		// past a full page, a search goes to the host
		searchSessions() {
			flow.state.sessionsLoading = true
		},
		setFolderOpen(cwd, open) {
			const others = flow.state.prefs.openFolders.filter((path) => path !== cwd)
			flow.state.prefs.openFolders = open ? [...others, cwd] : others
		},
		setSidebarView(view) {
			Object.assign(flow.state.prefs, view)
		},
	}
	const { el, unmount } = mount(t, SessionSidebar, {}, flow)
	assert.ok(el.textContent.includes("Loading"))
	assert.ok(!el.textContent.includes("No chats yet"))
	flow.state.sessionsLoading = false
	await nextTick()
	assert.ok(!el.textContent.includes("Loading"))
	assert.ok(el.textContent.includes("No chats yet"))

	// the search sits in the list's header
	const button = (title) => el.querySelector(`button[title='${title}']`)
	flow.state.sessions = [{ session_id: "s1", title: "Alpha" }]
	await nextTick()
	button("Search chats").click()
	await nextTick()
	await typeSearch(t, el, "beta")
	assert.ok(el.textContent.includes("Loading"))
	assert.ok(!el.textContent.includes("No matches"))
	flow.state.sessionsLoading = false
	await nextTick()
	assert.ok(el.textContent.includes("No matches"))

	// chats without a folder list flat
	const rows = () => [...el.querySelectorAll("[data-stub=SidebarItem]")]
	const labels = () => rows().map((row) => row.textContent.trim())
	const click = async (label) => {
		rows().find((row) => row.textContent.trim() === label).querySelector("button").click()
		await nextTick()
	}
	button("Close search").click()
	await nextTick()
	t.mock.timers.tick(200) // the cleared query's debounce
	await settle()
	assert.deepEqual(labels(), ["New chat", "Alpha", "Settings"])
	assert.ok(el.textContent.includes("Sessions") && !el.textContent.includes("Workspaces"))

	// with one, under its workspace, most recent first, the latest five and the open chat
	const app = Array.from({ length: 7 }, (_, i) => ({ session_id: `a${i}`, title: `App ${i}`, cwd: "/w/app" }))
	flow.state.sessions = [app[0], { session_id: "b", title: "Api work", cwd: "/w/api" }, ...app.slice(1)]
	flow.state.sessionId = "a6" // the chat on screen opens its workspace
	flow.state.session = { config: { cwd: "/w/app" } }
	await settle()
	const workspaces = ["app", "App 0", "App 1", "App 2", "App 3", "App 4", "App 6", "Show 1 more", "api"]
	assert.deepEqual(labels(), ["New chat", ...workspaces, "Settings"])
	assert.ok(el.textContent.includes("Workspaces"))

	// a hovered chat's card shows its whole title and its workspace
	const card = () => el.querySelector("[data-card]")
	const trigger = rows().find((row) => row.textContent.trim() === "App 1").querySelector("[data-stub=HoverCard]")
	trigger.dispatchEvent(new window.PointerEvent("pointerenter"))
	await nextTick()
	assert.deepEqual([...card().firstElementChild.children].map((line) => line.textContent.trim()), ["App 1", "app"])
	trigger.dispatchEvent(new window.PointerEvent("pointerleave"))
	await nextTick()
	assert.equal(card(), null)
	// a press on the row puts its card away, even one still in its hover dwell, until the pointer leaves
	const chatRow = trigger.closest("[data-stub=SidebarItem]")
	trigger.dispatchEvent(new window.PointerEvent("pointerenter"))
	await nextTick()
	chatRow.dispatchEvent(new window.PointerEvent("pointerdown", { bubbles: true }))
	await nextTick()
	assert.equal(card(), null)
	trigger.dispatchEvent(new window.PointerEvent("pointerenter"))
	await nextTick()
	assert.equal(card(), null)
	chatRow.dispatchEvent(new window.PointerEvent("pointerleave"))
	trigger.dispatchEvent(new window.PointerEvent("pointerenter"))
	await nextTick()
	assert.ok(card())
	trigger.dispatchEvent(new window.PointerEvent("pointerleave"))
	await nextTick()
	// and a workspace's, its name and folder
	const folderTrigger = rows().find((row) => row.textContent.trim() === "app").querySelector("[data-stub=HoverCard]")
	folderTrigger.dispatchEvent(new window.PointerEvent("pointerenter"))
	await nextTick()
	assert.deepEqual([...card().firstElementChild.children].map((line) => line.textContent.trim()), ["app", "/w/app"])
	folderTrigger.dispatchEvent(new window.PointerEvent("pointerleave"))
	await nextTick()
	await click("Show 1 more")
	assert.deepEqual(labels().slice(7, 10), ["App 5", "App 6", "Show less"])
	await click("api")
	await click("app")
	t.mock.timers.runAll() // the folded rows leave once their animation's frames pass
	assert.deepEqual(labels(), ["New chat", "app", "api", "Api work", "Settings"])
	assert.deepEqual(flow.state.prefs.openFolders, ["/w/api"])

	// a search opens every workspace with a match
	button("Search chats").click()
	await nextTick()
	await typeSearch(t, el, "app 5")
	assert.deepEqual(labels(), ["New chat", "app", "App 5", "Settings"])
	assert.equal(rows()[1].querySelector("button").getAttribute("aria-expanded"), "true")
	assert.equal(el.querySelector("input").getAttribute("aria-label"), "Search chats") // not its close button's title
	await click("app") // the search holds it open: a click folds nothing, now or after
	assert.deepEqual(flow.state.prefs.openFolders, ["/w/api"])

	// an empty search closes once it loses focus
	button("Close search").click()
	await nextTick()
	button("Search chats").click()
	await nextTick()
	el.querySelector("input").dispatchEvent(new window.Event("blur"))
	await nextTick()
	assert.ok(button("Search chats") && !el.querySelector("input"))

	// the filters menu lists the chats in one list; a drag puts a chat where it's dropped and
	// switches to manual order, where each keeps its place and a new chat lands on top
	t.mock.timers.tick(200) // the cleared query's debounce
	await settle()
	const pickView = async (label) => {
		const item = () => [...el.querySelectorAll("[role=menuitem]")].find((option) => option.textContent === label)
		if (!item()) button("Group and sort").click()
		await nextTick()
		item().click()
		await nextTick()
	}
	await pickView("In one list")
	assert.deepEqual(labels().slice(1, 4), ["App 0", "Api work", "App 1"])
	const row = (label) => rows().find((item) => item.textContent.trim() === label)
	const pointer = (type, target, init = {}) => {
		// Vue skips the row's drag listener for a press in the millisecond the row was made, once its
		// card-hold listener has seen it; a person's press always comes later
		if (type === "pointerdown") for (const at = Date.now(); Date.now() === at; );
		target.dispatchEvent(
			new window.PointerEvent(type, {
				pointerType: "mouse",
				clientY: type === "pointerdown" ? 100 : 0,
				buttons: type === "pointerup" ? 0 : 1,
				bubbles: true,
				...init,
			}),
		)
	}
	t.after(() => delete document.elementFromPoint)
	const drag = async (from, to) => {
		document.elementFromPoint = () => row(to).querySelector("button") // jsdom has no layout: the pointer is over `to`, above its middle
		pointer("pointerdown", row(from))
		pointer("pointermove", window)
		await nextTick()
		assert.ok(row(to).classList.contains("drop-before"))
		pointer("pointerup", window)
		await nextTick()
	}
	// a press whose release never comes drops nothing: a move with no button held ends it, and
	// a ctrl-click (a Mac's right click) never starts one
	document.elementFromPoint = () => row("App 0").querySelector("button")
	pointer("pointerdown", row("App 1"))
	pointer("pointermove", window)
	await nextTick()
	assert.ok(row("App 0").classList.contains("drop-before"))
	pointer("pointermove", window, { buttons: 0 })
	await nextTick()
	assert.ok(!row("App 0").classList.contains("drop-before"))
	pointer("pointerdown", row("App 1"), { ctrlKey: true })
	pointer("pointermove", window)
	await nextTick()
	assert.ok(!row("App 0").classList.contains("drop-before"))
	pointer("pointerup", window)
	assert.equal(flow.state.prefs.sidebarOrder, undefined)
	flow.state.prefs.chatOrder = ["b"] // an older manual order gives way to the one on screen
	await drag("App 6", "App 0")
	assert.deepEqual(labels().slice(1, 4), ["App 6", "App 0", "Api work"])
	assert.equal(flow.state.prefs.sidebarOrder, "manual")
	await pickView("Workspace")
	await drag("api", "app")
	assert.deepEqual(labels(), ["New chat", "api", "Api work", "app", "Settings"])

	// a list with pages still to load can't be reordered: a drop saves every chat's place
	flow.state.sessionsMore = true
	await nextTick()
	assert.equal(row("Api work").querySelector("button").getAttribute("data-reorder"), null)
	flow.state.sessionsMore = false
	await nextTick()

	// a row's own buttons act alone and start no drag: the new-chat button leaves its workspace
	// folded, and a chat's ••• doesn't open the chat
	for (const [label, title] of [["app", "New chat in app"], ["Api work", "Session options"]]) {
		const own = row(label).querySelector(`button[title='${title}']`)
		pointer("pointerdown", own)
		pointer("pointermove", window)
		await nextTick()
		assert.ok(!el.querySelector("aside").classList.contains("flow-reordering"))
		pointer("pointerup", window)
		own.click()
		await nextTick()
	}
	assert.deepEqual(opened, ["new chat in /w/app"])
	assert.deepEqual(labels(), ["New chat", "api", "Api work", "app", "Settings"])
	flow.state.sessions = [{ session_id: "n", title: "New one", cwd: "/w/api" }, ...flow.state.sessions]
	await settle()
	assert.deepEqual(labels(), ["New chat", "api", "New one", "Api work", "app", "Settings"])
	assert.equal(flow.state.prefs.chatOrder[0], "n")

	// a new chat on screen opens its folded workspace
	flow.state.sessions = [{ session_id: "a7", title: "App 7", cwd: "/w/app" }, ...flow.state.sessions]
	flow.state.sessionId = "a7"
	await settle()
	const appChats = () => labels().slice(labels().indexOf("app") + 1, -1)
	assert.deepEqual(appChats(), ["App 7", "App 6", "App 0", "App 1", "App 2", "App 3", "App 4", "App 5", "Show less"])

	// a chat dropped beside the open chat shown past the first five stays in view
	await click("Show less")
	flow.state.sessionId = "a5"
	await settle()
	assert.deepEqual(appChats(), ["App 7", "App 6", "App 0", "App 1", "App 2", "App 5", "Show 2 more"])
	await drag("App 7", "App 5")
	assert.deepEqual(appChats(), ["App 6", "App 0", "App 1", "App 2", "App 3", "App 4", "App 7", "App 5", "Show less"])

	// a phone's workspace shows no new-chat button: a long press opens its menu, as a chat's does.
	// The open drawer's backdrop comes once the script knows the frame is narrow
	const backdrop = () => el.querySelector("button[aria-label='Close sidebar']")
	assert.equal(backdrop(), null)
	layout.phone = layout.narrow = true
	t.after(() => (layout.phone = layout.narrow = false))
	await nextTick()
	assert.ok(backdrop())
	assert.equal(el.querySelector("button[title='New chat in app']"), null)
	// a row's open menu joins its text: each row is held from before its press
	const [workspace, chat] = [row("app"), row("App 6")]
	const press = (target) => target.dispatchEvent(new window.PointerEvent("pointerdown", { pointerType: "touch", bubbles: true }))
	const menu = (target) => [...target.querySelectorAll("[role=menuitem]")].map((item) => item.textContent)
	press(workspace)
	t.mock.timers.tick(500)
	await nextTick()
	assert.deepEqual(menu(workspace), ["New chat"])
	workspace.querySelector("[role=menuitem]").click()
	await nextTick()
	assert.equal(opened.at(-1), "new chat in /w/app")
	press(chat)
	t.mock.timers.tick(500)
	await nextTick()
	assert.deepEqual(menu(chat), ["Rename", "Delete"])
	layout.phone = layout.narrow = false
	await nextTick()

	// a drag in flight when the sidebar goes ends there, dropping nothing
	const order = [...flow.state.prefs.chatOrder]
	document.elementFromPoint = () => row("App 6").querySelector("button")
	pointer("pointerdown", row("App 0"))
	pointer("pointermove", window)
	await nextTick()
	unmount()
	pointer("pointerup", window)
	assert.deepEqual(flow.state.prefs.chatOrder, order)

	// a host showing a page in the chat's place has its say first: a chat changes once it lets go
	const asks = []
	const host = mount(t, SessionSidebar, { beforeSwitch: () => new Promise((resolve) => asks.push(resolve)) }, flow)
	const hostRow = (label) => [...host.el.querySelectorAll("[data-stub=SidebarItem]")].find((item) => item.textContent.trim() === label)
	opened.length = 0
	hostRow("New chat").querySelector("button").click()
	hostRow("Api work").querySelector("button").click()
	await settle()
	assert.deepEqual(opened, [])
	asks[0](false)
	asks[1](true)
	await settle()
	assert.deepEqual(opened, ["b"])
})

test("a daemon's workspaces list by their own names, a new or empty one on top, chats in none last; a new one opens with a chat, and a workspace's menu renames or deletes it", async (t) => {
	t.mock.timers.enable({ apis: ["setTimeout"] })
	const asked = []
	dialog.prompt = dialog.confirm = (options) => asked.push(options)
	t.after(() => {
		delete dialog.prompt
		delete dialog.confirm
	})
	const done = []
	const flow = {
		options: {},
		state: reactive({
			sessions: [
				// started through a link to the workspace's folder
				{ session_id: "a", title: "Fix the cart", cwd: "/w/shop-link", workspace: "/w/shop" },
				{ session_id: "b", title: "Old notes", cwd: "/w/gone", workspace: null },
			],
			sessionsLoading: false,
			sessionsMore: false,
			sessionId: null,
			folders: [
				{ path: "/w/shop", name: "Shop" },
				{ path: "/w/empty", name: "empty" },
			],
			prefs: { openFolders: ["/w/shop"] },
		}),
		sessionTitle: (session) => session.title,
		folderName: (path) => flow.state.folders.find((folder) => folder.path === path)?.name ?? path.split("/").pop(),
		searchSessions() {},
		setFolderOpen() {},
		setSidebarView(view) {
			Object.assign(flow.state.prefs, view)
		},
		startNewChat: ({ cwd }) => done.push(["new chat", cwd]),
		pickFolder: async () => "/w/new",
		async addFolder(path) {
			flow.state.folders = [...flow.state.folders, { path, name: "new" }]
			return flow.state.folders.at(-1)
		},
		renameFolder: (path, name) => done.push(["rename", path, name]),
		removeFolder: (path) => done.push(["delete", path]),
	}
	const { el } = mount(t, SessionSidebar, {}, flow)
	const rows = () => [...el.querySelectorAll("[data-stub=SidebarItem]")]
	const labels = () => rows().map((row) => row.textContent.trim())
	const row = (label) => rows().find((item) => item.textContent.trim() === label)
	const button = (title) => el.querySelector(`button[title='${title}']`)
	assert.deepEqual(labels(), ["New chat", "empty", "Shop", "Fix the cart", "Old notes", "Settings"])
	assert.ok(el.textContent.includes("Ungrouped"))
	assert.ok(row("Shop").querySelector("button[title='Workspace options']"))

	// a folder picked for a new one becomes a workspace at once, on top, with a chat in it
	button("New workspace").click()
	await settle()
	assert.deepEqual(done, [["new chat", "/w/new"]])
	assert.deepEqual(labels().slice(1, 3), ["new", "empty"])

	// a manual order starts from the order on screen
	const shown = labels()
	button("Group and sort").click()
	await nextTick()
	;[...el.querySelectorAll("[role=menuitem]")].find((item) => item.textContent === "Manual").click()
	await nextTick()
	assert.equal(flow.state.prefs.sidebarOrder, "manual")
	assert.deepEqual(labels(), shown)

	// a search shows only the workspaces with a match
	button("Search chats").click()
	await nextTick()
	await typeSearch(t, el, "cart")
	assert.deepEqual(labels(), ["New chat", "Shop", "Fix the cart", "Settings"])
	button("Close search").click()
	t.mock.timers.tick(200)
	await settle()

	// each dialog keeps the workspace it was opened for
	layout.phone = layout.narrow = true
	t.after(() => (layout.phone = layout.narrow = false))
	await nextTick()
	const shop = row("Shop") // held: its open menu joins its text
	shop.dispatchEvent(new window.PointerEvent("pointerdown", { pointerType: "touch", bubbles: true }))
	t.mock.timers.tick(500)
	await nextTick()
	const items = [...shop.querySelectorAll("[role=menuitem]")]
	assert.deepEqual(items.map((item) => item.textContent), ["New chat", "Rename", "Delete"])
	items[1].click()
	items[2].click()
	assert.equal(asked[0].fields[0].defaultValue, "Shop")
	assert.ok(asked[1].message.includes("Shop") && asked[1].message.includes("Ungrouped"))
	asked[0].onConfirm({ values: { name: " Store " } })
	asked[1].actions.at(-1).onClick()
	assert.deepEqual(done.slice(1), [["rename", "/w/shop", "Store"], ["delete", "/w/shop"]])
})

test("the model list says it is loading, not that no provider is connected, then names each provider's models under it", async (t) => {
	const flow = { state: reactive({ models: [], modelsLoading: true, conversation: {}, prefs: {} }) }
	const { el } = mount(t, ModelPalette, {}, flow)
	assert.ok(el.textContent.includes("Loading"))
	assert.ok(!el.textContent.includes("No models yet"))
	flow.state.modelsLoading = false
	await nextTick()
	assert.ok(!el.textContent.includes("Loading"))
	assert.ok(el.textContent.includes("No models yet"))

	// a provider's own name, else the id spelled out; the current one ticked
	flow.state.models = [
		{ name: "codex/gpt-6-sol", provider: "codex" },
		{ name: "openrouter/anthropic/claude-opus-4.5", provider: "openrouter", display_name: "Anthropic: Claude Opus 4.5" },
		{ name: "openrouter/deepseek/deepseek-v4-flash", provider: "openrouter", display_name: "DeepSeek: DeepSeek V4 Flash" },
	]
	flow.state.prefs.lastModel = "openrouter/deepseek/deepseek-v4-flash"
	await nextTick()
	const lines = (root) => [...root.querySelectorAll(".flow-palette-list > *")].map((node) => node.textContent.trim())
	assert.deepEqual(lines(el), ["codex", "GPT-6 Sol", "openrouter", "Anthropic: Claude Opus 4.5", "DeepSeek: DeepSeek V4 Flash"])
	assert.equal(el.querySelector("[aria-current=true]").textContent.trim(), "DeepSeek: DeepSeek V4 Flash")

	// hung from the model button it searches with a field of its own, by each word of a name or id
	t.mock.timers.enable({ apis: ["setTimeout"] })
	const dropdown = mount(t, ModelPalette, { dropdown: true }, flow)
	const field = dropdown.el.querySelector("input")
	assert.equal(document.activeElement, field)
	for (const [typed, shown] of [
		["opus 4.5", ["openrouter", "Anthropic: Claude Opus 4.5"]],
		["gpt-6", ["codex", "GPT-6 Sol"]],
		["zzz", ["No matching models"]],
		["acme/x-1", ['Use "acme/x-1"']],
	]) {
		field.value = typed
		field.dispatchEvent(new window.Event("input"))
		await nextTick() // the search's watcher sets its timer
		t.mock.timers.tick(150)
		await nextTick()
		assert.deepEqual(lines(dropdown.el), shown, typed)
	}
})

test("the file picker says it is loading until its first listing arrives, and opens a folder its search finds", async (t) => {
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

	// the composer drops the "@"'s query when the list opens a folder
	t.mock.timers.enable({ apis: ["setTimeout"] })
	const draft = reactive({ query: "chat" })
	const listed = []
	const finder = {
		explorerCwd: () => "/w",
		searchFiles: async () => ({ path: "/w", matches: ["src/chat/", "src/chat/chat.js"], truncated: false }),
		listFiles: async (path) => {
			listed.push(path)
			return { path: `/w/${path}`, entries: [{ name: "send.js", type: "file" }] }
		},
	}
	const host = { render: () => h(FileMentionPalette, { query: draft.query, onBrowse: () => (draft.query = "") }) }
	const picker = mount(t, host, {}, finder)
	await settle()
	const rows = () =>
		[...picker.el.querySelectorAll("[data-palette-item]")].map((row) => [
			row.querySelector("[data-stub=FeatherIcon]").getAttribute("name"),
			row.textContent.trim(),
		])
	assert.deepEqual(rows(), [["folder", "src/chat"], ["file-text", "src/chat/chat.js"]])
	picker.el.querySelector("[data-palette-item]").click()
	await nextTick()
	assert.equal(draft.query, "")
	t.mock.timers.tick(150)
	await settle()
	assert.deepEqual(listed, ["src/chat"])
	assert.deepEqual(rows(), [["corner-left-up", ".."], ["file-text", "send.js"]])
	assert.ok(picker.el.textContent.includes("src/chat")) // its title
})

test("the files panel says it is loading until its tree, change list or search results arrive", async (t) => {
	t.mock.timers.enable({ apis: ["setTimeout"] })
	let list, changes
	const flow = {
		state: reactive({ workspace: { tabs: [], active: null }, prefs: {} }),
		explorerCwd: () => "/w",
		listFiles: () => new Promise((resolve) => (list = resolve)),
		gitChanges: () => new Promise((resolve) => (changes = resolve)),
		searchFiles: () => new Promise(() => {}),
	}
	const tree = mount(t, FilesBar, { open: true, mode: "files" }, flow)
	assert.ok(tree.el.textContent.includes("Loading"))
	list({ path: "/w", entries: [] })
	await settle()
	assert.ok(!tree.el.textContent.includes("Loading"))
	assert.ok(tree.el.textContent.includes("Empty folder"))
	// a search in flight shows the spinner with its own word
	await typeSearch(t, tree.el, "app")
	assert.ok(tree.el.textContent.includes("Searching…"))
	assert.ok(tree.el.querySelector("[data-stub=Spinner]"))

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

test("the providers list says it is loading, and a sign-in check still in flight never lands on the provider opened next", async (t) => {
	t.mock.timers.enable({ apis: ["setInterval"] })
	t.mock.method(window, "open", () => null)
	let list
	const listed = new Promise((resolve) => (list = resolve))
	let answer
	const oauth = (id, name) => ({ id, name, auth_methods: ["oauth"], configured: false })
	const flow = {
		client: {
			providers: () => listed,
			oauthStart: async () => ({ authorize_url: "https://sign.in", status: "pending" }),
			oauthStatus: () => new Promise((resolve) => (answer = resolve)),
		},
	}
	const { el } = mount(t, ProvidersDialog, {}, flow)
	assert.ok(el.textContent.includes("Loading"))
	list({ providers: [oauth("alpha", "Alpha"), oauth("beta", "Beta")] })
	await settle()
	assert.ok(!el.textContent.includes("Loading"))
	const button = (label) => [...el.querySelectorAll("button")].find((b) => b.textContent.trim() === label)
	button("Alpha").click()
	await nextTick()
	button("Sign in").click()
	await settle()
	assert.ok(el.textContent.includes("Waiting for sign-in"))
	t.mock.timers.tick(1500) // the poll asks about Alpha

	el.querySelector("[data-stub='PalettePanel']").dispatchEvent(new window.Event("back"))
	await nextTick()
	button("Beta").click()
	await nextTick()
	answer({ status: "pending" })
	await settle()
	assert.ok(button("Sign in"))
	assert.ok(!el.textContent.includes("Waiting for sign-in"))
})

test("the skills settings say they are loading until the folders are read, and a new skill can't take a name already in its folder, listed or not", async (t) => {
	let list
	const listed = new Promise((resolve) => (list = resolve))
	const writes = []
	const flow = {
		state: reactive({ settingsOpen: true, sessionId: null, session: null, sessions: [], prefs: {} }),
		client: {
			skillFiles: () => listed,
			async readSkill(path) {
				// "triage" was made after the list loaded (another tab, the agent), so it isn't listed
				if (path === "/g/triage/SKILL.md") return { path, content: "---\nname: triage\n---\n" }
				throw new FlowAPIError(404, "file not found")
			},
			async writeSkill(path) {
				writes.push(path)
				return { path }
			},
		},
		notify() {},
	}
	const { el } = mount(t, SettingsSkills, {}, flow)
	assert.ok(el.textContent.includes("Loading"))
	assert.ok(!el.textContent.includes("No global skills yet"))
	list({
		skills: [{ scope: "global", path: "/g/review/SKILL.md", name: "review", description: "Review", error: null }],
		roots: { global: "/g" },
	})
	await settle()
	assert.ok(!el.textContent.includes("Loading"))
	const button = (label) => [...el.querySelectorAll("button")].find((b) => b.textContent === label)
	const saveAs = async (name) => {
		const input = el.querySelector("input")
		input.value = name
		input.dispatchEvent(new window.Event("input"))
		await nextTick()
		button("Save").click()
		await settle()
	}
	button("New skill").click()
	await nextTick()
	await saveAs("review")
	assert.ok(el.textContent.includes("A global skill named “review” already exists."))
	await saveAs("triage")
	assert.ok(el.textContent.includes("A global skill named “triage” already exists."))
	assert.deepEqual(writes, [])
	await saveAs("fresh")
	assert.deepEqual(writes, ["/g/fresh/SKILL.md"])
})

test("the header says nothing in a new chat until its first message goes out, nor while a chat loads, and its menu renames or deletes the open chat, under the host's own items", async (t) => {
	const asked = []
	dialog.prompt = dialog.confirm = (options) => asked.push(options)
	t.after(() => {
		delete dialog.prompt
		delete dialog.confirm
	})
	const done = []
	const flow = {
		state: reactive({
			loading: false, sessionId: null, session: null, sessions: [], conversation: initialConversation(), prefs: {}, workspace: {},
		}),
		renameSession: (sid, title) => done.push(["rename", sid, title]),
		deleteSession: (sid) => done.push(["delete", sid]),
		folderName: (path) => ({ "/w/expenses": "Expenses app" })[path],
	}
	const { el } = mount(t, ChatHeader, {}, flow)
	const line = () => !el.querySelector("header").classList.contains("border-transparent")
	assert.ok(el.querySelector("button[title='Open panel']"))
	assert.ok(!el.textContent.includes("New chat"))
	assert.equal(line(), false)
	assert.equal(el.querySelector("button[title='Chat options']"), null, "a new chat has nothing to act on")
	// its first message names it and draws the line
	flow.state.conversation.sending = [{ key: "sending:1", entry: { type: "user_message", content: [{ type: "text", text: "count the todos" }], ts: 10 } }]
	await nextTick()
	assert.ok(el.textContent.includes("count the todos"))
	assert.equal(line(), true)
	// its folder before the title, or the host's own crumb in its place
	flow.state.prefs.cwd = "/w/expenses"
	await nextTick()
	assert.equal(el.querySelector("header div[title]").title, "/w/expenses / count the todos")
	assert.ok(el.textContent.includes("Expenses app")) // by its workspace's name
	const named = mount(t, ChatHeader, { crumb: { icon: "bot", label: "Reviewer" } }, flow).el
	assert.equal(named.querySelector("header div[title]").title, "Reviewer / count the todos")
	assert.ok(!named.textContent.includes("expenses"))
	flow.state.conversation.sending = []

	// a chat opened from its link: no title to seed until it arrives
	flow.state.sessionId = "s1"
	flow.state.loading = true
	await nextTick()
	assert.ok(!el.textContent.includes("New chat"))
	assert.equal(line(), true)
	flow.state.session = { title: "Quarterly report" }
	flow.state.loading = false
	await nextTick()
	assert.ok(el.textContent.includes("Quarterly report"))
	// one started through a link to its workspace's folder goes by the workspace's name
	flow.state.session.config = { cwd: "/w/expenses-link" }
	flow.state.sessions = [{ session_id: "s1", workspace: "/w/expenses" }]
	await nextTick()
	assert.ok(el.textContent.includes("Expenses app"))

	const host = mount(t, ChatHeader, { actions: [{ label: "Share" }] }, flow)
	const menu = () => host.el.querySelector("button[title='Chat options']")
	const items = () => [...host.el.querySelectorAll("[role=menuitem]")]
	menu().click()
	await nextTick()
	assert.deepEqual(items().map((item) => item.textContent), ["Share", "Rename", "Delete"])
	items()[1].click()
	items()[2].click()
	assert.equal(asked[0].fields[0].defaultValue, "Quarterly report")
	assert.ok(asked[1].message.includes("Quarterly report"))
	// another chat opening meanwhile: each dialog still acts on the chat it was opened for
	flow.state.sessionId = "s2"
	flow.state.session = { title: "Notes" }
	await nextTick()
	asked[0].onConfirm({ values: { title: " Q3 report " } })
	asked[1].actions.at(-1).onClick()
	assert.deepEqual(done, [["rename", "s1", "Q3 report"], ["delete", "s1"]])

	// a chat the user may only view has no menu
	flow.state.session = { title: "Their report", read_only: true }
	await nextTick()
	assert.equal(menu(), null)
})

test("the model button names the chat's own model and thinking level, never the last one picked while a chat loads", async (t) => {
	const conversation = reactive(initialConversation())
	const flow = {
		state: reactive({ loading: true, sessionId: "s1", conversation, models: [], prefs: { lastModel: "openai/gpt-old", lastEffort: "high" } }),
	}
	const { el } = mount(t, ModelButton, {}, flow)
	assert.ok(!el.textContent.includes("Old"))
	assert.ok(!el.textContent.includes("Choose Model"))
	conversation.model = "openai/gpt-6" // the chat's own, from the list or the loaded session
	flow.state.loading = false
	await nextTick()
	// its id spelled out, until the list gives its provider's own name
	assert.equal(el.querySelector("button").textContent.trim(), "GPT-6")
	flow.state.models = [{ name: "openai/gpt-6", provider: "openai", display_name: "OpenAI: GPT-6" }]
	await nextTick()
	assert.equal(el.querySelector("button").textContent.trim(), "OpenAI: GPT-6")
	// an open chat runs at its own thinking level (none: the provider's default); a new chat at the last one picked
	assert.ok(!el.textContent.includes("High"))
	flow.state.sessionId = null
	await nextTick()
	assert.ok(el.textContent.includes("High"))
})

function composerFlow(over = {}) {
	return {
		options: { requireCwd: false, maxAttachments: 10, skillsEnabled: false },
		state: reactive({
			prefs: { mode: "ask" }, sessionId: "s1", session: null, models: [], codeRefs: [], quotes: [], queued: [],
			skills: [], conversation: { running: true }, draft: null,
		}),
		clearCodeRefs() {},
		clearQuotes() {},
		notify() {},
		folderName: (path) => path.split("/").pop(),
		...over,
	}
}

const keydown = (target, init) =>
	target.dispatchEvent(new window.KeyboardEvent("keydown", { bubbles: true, cancelable: true, ...init }))

test("an IME's Enter and Escape stay with it, and Escape stops the run from the page, but not from a field, a dialog or a menu, or while its host hides it", async (t) => {
	let sends = 0
	let aborts = 0
	const flow = composerFlow({ send: async () => !!++sends, abort: () => aborts++ })
	const { el, vm } = mount(t, Composer, { commands: [], mentions: false }, flow)
	vm.prefill("今日は")
	await nextTick()
	const box = el.querySelector("textarea")

	keydown(box, { key: "Enter", isComposing: true })
	keydown(box, { key: "Enter", keyCode: 229 }) // Safari's, after compositionend
	keydown(box, { key: "Escape", isComposing: true })
	await settle()
	assert.equal(sends, 0)
	assert.equal(aborts, 0)
	assert.equal(box.value, "今日は")
	// a phone's return key starts a new line; its send button sends
	layout.phone = true
	t.after(() => (layout.phone = false))
	assert.equal(keydown(box, { key: "Enter" }), true)
	await settle()
	assert.equal(sends, 0)
	layout.phone = false
	keydown(box, { key: "Enter" })
	await settle()
	assert.equal(sends, 1)

	// from the page
	const outside = document.createElement("div")
	outside.innerHTML =
		'<input placeholder="Search chats"><div role="dialog"><button>Close</button></div><div role="menu"><button>Rename</button></div>'
	document.body.append(outside)
	t.after(() => outside.remove())
	for (const target of outside.querySelectorAll("input, button")) keydown(target, { key: "Escape" })
	keydown(document.body, { key: "Escape", isComposing: true })
	assert.equal(aborts, 0)
	// hidden by its host (inert), as /flow does under a page, the box stops nothing
	el.setAttribute("inert", "")
	keydown(document.body, { key: "Escape" })
	assert.equal(aborts, 0)
	el.removeAttribute("inert")
	keydown(document.body, { key: "Escape" })
	assert.equal(aborts, 1)
})

test("the ask-for-changes field takes focus and leaves an IME's Enter and Escape to it", async (t) => {
	const answers = []
	const flow = { options: {}, answerApproval: (...answer) => answers.push(answer) }
	const { el } = mount(t, ApprovalCard, { call: { id: "c1", name: "bash", args: { command: "pwd" } } }, flow)
	;[...el.querySelectorAll("button")].find((b) => b.textContent === "Ask for changes").click()
	await nextTick()
	await nextTick()
	const field = el.querySelector("textarea")
	assert.equal(document.activeElement, field)
	field.value = "use 日本"
	field.dispatchEvent(new window.Event("input"))

	keydown(field, { key: "Enter", isComposing: true })
	keydown(field, { key: "Escape", keyCode: 229 })
	await nextTick()
	assert.deepEqual(answers, [])
	assert.ok(el.querySelector("textarea"))
	keydown(field, { key: "Enter" })
	assert.deepEqual(answers, [["c1", "use 日本"]])
})

test("a spreadsheet range pastes as its text, a screenshot as a picture", async (t) => {
	const createObjectURL = URL.createObjectURL
	URL.createObjectURL = () => "blob:shot"
	t.after(() => (URL.createObjectURL = createObjectURL))
	const { el } = mount(t, Composer, { commands: [], mentions: false }, composerFlow())
	const paste = (data) => {
		const event = new window.Event("paste", { bubbles: true, cancelable: true })
		const png = new window.File(["png"], "image.png", { type: "image/png" })
		event.clipboardData = {
			items: [{ kind: "file", type: "image/png", getAsFile: () => png }],
			getData: (type) => data[type] ?? "",
		}
		el.querySelector("textarea").dispatchEvent(event)
		return event.defaultPrevented
	}

	// Excel and LibreOffice put a picture of the cells beside their text and HTML
	assert.equal(paste({ "text/plain": "Item\tQty\nA\t2", "text/html": "<table><tr><td>Item</td></tr></table>" }), false)
	await nextTick()
	assert.equal(el.querySelector("img"), null)
	// a screenshot, or an image copied from a page, has no text of its own
	assert.equal(paste({}), true)
	assert.equal(paste({ "text/plain": "https://e.x/a.png", "text/html": '<meta charset="utf-8"><img src="https://e.x/a.png">' }), true)
})

test("a palette's Enter picks from the rows that answer its search, whose top row takes the highlight, the keyboard's row keeps it under a resting pointer, and a click on the list leaves the focus in the composer; inside a view its host hides, it takes no keys", async (t) => {
	const PalettePanel = await loadComponent("PalettePanel")
	globalThis.MutationObserver = dom.window.MutationObserver
	t.after(() => delete globalThis.MutationObserver)
	const picked = []
	const list = reactive({ query: "", busy: false, rows: ["openai/gpt-5"] })
	const row = (name) => h("button", { key: name, "data-palette-item": "", onClick: () => picked.push(name) }, name)
	const Host = {
		// a provider's page puts a form field in the panel
		render: () => h(PalettePanel, { title: "Models", query: list.query, busy: list.busy }, () => [...list.rows.map(row), h("input")]),
	}
	const { el } = mount(t, Host, {}, {})
	await settle()

	keydown(document.body, { key: "Enter", isComposing: true }) // an IME's, picking its candidate
	list.busy = true // "opus" typed, its rows not in yet
	await nextTick()
	keydown(document.body, { key: "Enter" })
	assert.deepEqual(picked, [])
	list.rows = ["anthropic/claude-opus"]
	list.busy = false
	await settle()
	assert.deepEqual(picked, ["anthropic/claude-opus"])
	// inside a view its host hides (inert), as /flow's chat under a page, Enter picks nothing
	el.setAttribute("inert", "")
	keydown(document.body, { key: "Enter" })
	el.removeAttribute("inert")
	assert.deepEqual(picked, ["anthropic/claude-opus"])

	// the keyboard walks past the list's edge, scrolling another row under the resting pointer
	list.rows = ["a", "b", "c"]
	await settle()
	const pointer = (type, name, clientX) =>
		[...el.querySelectorAll("[data-palette-item]")]
			.find((item) => item.textContent === name)
			.dispatchEvent(new window.PointerEvent(type, { bubbles: true, clientX, clientY: 10 }))
	const active = () => el.querySelector("[data-palette-active]").textContent
	pointer("pointermove", "a", 5)
	keydown(document.body, { key: "ArrowDown" })
	pointer("pointerover", "c", 5)
	pointer("pointermove", "c", 5)
	assert.equal(active(), "b")
	pointer("pointermove", "c", 6)
	assert.equal(active(), "c")

	// a new search hands the highlight to its top row, though the old row still answers it
	list.query = "b"
	list.busy = true
	await nextTick()
	list.rows = ["b", "c"]
	list.busy = false
	await settle()
	assert.equal(active(), "b")

	// a press on a row keeps the composer focused; a form field still takes the focus
	const press = (target) => {
		const event = new window.MouseEvent("mousedown", { bubbles: true, cancelable: true })
		target.dispatchEvent(event)
		return event.defaultPrevented
	}
	assert.equal(press(el.querySelector("[data-palette-item]")), true)
	assert.equal(press(el.querySelector("input")), false)
})

test("a message that overflows once the thread narrows gets its Show more", async (t) => {
	const UserBubble = await loadComponent("UserBubble")
	let resized = null
	globalThis.ResizeObserver = class {
		constructor(callback) {
			resized = callback
		}
		observe() {}
		disconnect() {}
	}
	t.after(() => delete globalThis.ResizeObserver)
	// jsdom has no layout: the text's full height against the 12-line clamp's
	let full = 200
	const proto = dom.window.HTMLElement.prototype
	Object.defineProperty(proto, "scrollHeight", { configurable: true, get: () => full })
	Object.defineProperty(proto, "clientHeight", { configurable: true, get: () => 240 })
	t.after(() => {
		delete proto.scrollHeight
		delete proto.clientHeight
	})
	const flow = { options: {}, capabilities: {}, state: reactive({ sessionId: "s1", skills: [] }) }
	const { el } = mount(t, UserBubble, { entry: { type: "user_message", seq: 1, content: "a long message" } }, flow)
	assert.ok(!el.textContent.includes("Show more"))

	full = 300 // a panel opened beside the thread
	resized()
	await nextTick()
	assert.ok(el.textContent.includes("Show more"))
})

test("Copy says Copied only once the text reached the clipboard, in a host's own label too", async (t) => {
	const CopyButton = await loadComponent("CopyButton")
	const { el } = mount(t, CopyButton, { text: "hello" }, {})
	const button = el.querySelector("button")
	// plain http has no Clipboard API, and the copy command can fail too
	document.execCommand = () => false
	t.after(() => delete document.execCommand)
	button.click()
	await settle()
	assert.equal(button.title, "Copy")
	document.execCommand = (command) => command === "copy"
	button.click()
	await settle()
	assert.equal(button.title, "Copied")

	// a host's label and icon, and the label it shows once copied
	const label = ({ copied }) => (copied ? "Copied" : "Copy link")
	const host = mount(t, { render: () => h(CopyButton, { text: "http://site/flow/s/1", icon: "link" }, label) }, {}, {})
	const link = host.el.querySelector("button")
	assert.equal(link.textContent.trim(), "Copy link")
	assert.equal(host.el.querySelector("[data-stub=FeatherIcon]").getAttribute("name"), "link")
	link.click()
	await settle()
	assert.equal(link.textContent.trim(), "Copied")
})

test("the web app shows its connect form when the daemon refuses the token, and connects with the right one", async (t) => {
	const App = await loadComponent("App", new URL("../../app/src/App.vue", import.meta.url))
	const saved = { "flow.ui.connection": JSON.stringify({ baseUrl: "", token: "rotated" }) }
	globalThis.localStorage = { getItem: (key) => saved[key] ?? null, setItem: (key, value) => (saved[key] = value) }
	t.after(() => delete globalThis.localStorage)
	// like a daemon run with FLOW_AUTH_TOKEN: /healthz answers anyone, the API only the token
	t.mock.method(globalThis, "fetch", async (url, init) => {
		if (new URL(url).pathname === "/healthz") return Response.json({ ok: true })
		if (init.headers.Authorization !== "Bearer s3cret") return Response.json({ detail: "unauthorized" }, { status: 401 })
		return Response.json({ sessions: [] })
	})
	const { el } = mount(t, App, {}, null)
	await settle()
	assert.equal(el.querySelector("[data-stub='FlowChat']"), null)
	assert.ok(el.textContent.includes("The daemon refused the auth token."))

	const token = el.querySelector("input[type='password']")
	token.value = "s3cret"
	token.dispatchEvent(new window.Event("input"))
	el.querySelector("form").dispatchEvent(new window.Event("submit"))
	await settle()
	assert.ok(el.querySelector("[data-stub='FlowChat']"))
	assert.equal(JSON.parse(saved["flow.ui.connection"]).token, "s3cret")
})
