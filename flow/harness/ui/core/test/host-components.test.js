import assert from "node:assert/strict"
import test from "node:test"

import { JSDOM } from "jsdom"

// Vue's DOM runtime captures document at import time.
const dom = new JSDOM("<body></body>", { url: "http://localhost" })
for (const name of ["window", "document", "Document", "Element", "SVGElement", "HTMLElement"]) {
	globalThis[name] = dom.window[name]
}
dom.window.HTMLElement.prototype.scrollIntoView = () => {}
const { createApp, h, nextTick, reactive } = await import("vue")
const { loadComponent } = await import("./helpers/components.js")
const Composer = await loadComponent("Composer")
const ApprovalCard = await loadComponent("ApprovalCard")
const ToolGroup = await loadComponent("ToolGroup")

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
		state: { conversation: {} },
		answerApproval: (...answer) => answers.push(answer),
	}
	const { el } = mount(t, ApprovalCard, { seq: 1, calls: [{ id: "c1", name: "update_document", args }] }, flow)
	assert.ok(el.textContent.includes("Update invoice?"))
	assert.equal(el.querySelector("[data-test=args] dd").textContent, "Paid")
	assert.equal(el.querySelector("pre"), null)
	for (const label of ["Approve", "Deny"]) {
		[...el.querySelectorAll("button")].find((button) => button.textContent === label).click()
	}
	assert.deepEqual(answers, [["c1", "Approve"], ["c1", "Deny"]])
})

test("standalone approvals keep command text and edit diffs", (t) => {
	const { el } = mount(t, ApprovalCard, { seq: 1, calls: [
		{ id: "bash", name: "bash", args: { command: "pwd" } },
		{ id: "edit", name: "edit", args: { path: "a.txt", edits: [{ old: "before", new: "after" }] } },
	] }, { state: { conversation: {} } })
	assert.ok(el.textContent.includes("Run this command?"))
	assert.ok(el.textContent.includes("Apply 1 edit to a.txt?"))
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
