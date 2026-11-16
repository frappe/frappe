import { pinia } from "../support/component"

import { setActivePinia } from "pinia"
import { computed, defineComponent, h, onUnmounted, reactive, ref } from "vue"

import StudioComponentRenderer from "@/components/StudioComponentRenderer.vue"
import { setComponentScriptImporters, unregisterStudioComponentScripts } from "@/data/studioComponentScripts"
import { registerGlobalComponents } from "@/globals"
import useComponentStore from "@/stores/componentStore"
import getBlockTemplate from "@/utils/blockTemplate"
import { getEditorProps, validateComponentScript, type ComponentScript } from "@/utils/componentScript"
import { getPropsReadOnlyReason, setScriptProp } from "@/utils/componentScriptProps"
import { getBlockInstance } from "@/utils/serializer"

const COMPONENT_ID = "cypress_counter"

const unmounted: string[] = []
const counterScript: ComponentScript = {
	props: {
		title: { type: String, required: true },
		step: { type: Number, default: 1 },
	},
	emits: ["change"],
	setup(props, { emit }) {
		const count = ref(0)
		const note = ref("")
		const label = computed(() => `${props.title}: ${count.value}`)
		function add() {
			count.value += props.step
			emit("change", count.value)
		}
		onUnmounted(() => unmounted.push(props.title))
		return { count, note, label, add }
	},
}

function counterDoc(id: string) {
	const block = {
		...getBlockTemplate("container"),
		componentId: `${id}-root`,
		children: [
			{
				componentName: "Button",
				componentId: `${id}-add`,
				componentProps: { label: "{{ label }}" },
				componentEvents: { click: { event: "click", action: "Run Script", script: "add()" } },
			},
			{
				componentName: "TextInput",
				componentId: `${id}-note`,
				componentProps: { modelValue: { $type: "variable", name: "note" } },
			},
			{
				componentName: "Button",
				componentId: `${id}-echo`,
				componentProps: { label: "{{ props.title }} says {{ note }}" },
			},
		],
	}
	return { name: id, component_id: id, component_name: id, block: JSON.stringify(block), inputs: [] }
}

function counterBlock(id: string, componentProps: Record<string, any>) {
	return getBlockInstance({
		componentName: COMPONENT_ID,
		componentId: id,
		isStudioComponent: true,
		componentProps,
	})
}

// Load a script as an app build does, so no test needs a server.
function setComponent(script: unknown, doc: Record<string, any> = counterDoc(COMPONENT_ID)) {
	setComponentScriptImporters({ [doc.component_id]: async () => ({ default: script }) })
	return cy.wrap(useComponentStore().setComponents([doc as any]))
}

const global = { plugins: [pinia, { install: registerGlobalComponents }] }

describe("component scripts", () => {
	beforeEach(() => {
		setActivePinia(pinia)
		unmounted.length = 0
	})
	afterEach(() => {
		useComponentStore().removeCachedComponent(COMPONENT_ID)
		unregisterStudioComponentScripts()
	})

	it("gives each instance its own props, state and events, without a page or a router", () => {
		const scope = reactive({ firstTitle: "First" })
		const shown = ref(true)
		const changes = { first: cy.stub(), second: cy.stub() }
		// `click` is not in the script's emits, so it is a DOM event of the component's root block
		const rootClicks = { first: cy.stub(), second: cy.stub() }
		const blocks = {
			first: counterBlock("first", { title: "{{ firstTitle }}" }),
			second: counterBlock("second", { title: "Second", step: 5 }),
		}
		setComponent(counterScript)
		cy.mount(
			defineComponent({
				setup: () => () =>
					shown.value &&
					(["first", "second"] as const).map((name) =>
						h(StudioComponentRenderer, {
							key: name,
							studioComponent: blocks[name],
							evaluationContext: scope,
							listeners: { change: changes[name], click: rootClicks[name] },
						}),
					),
			}),
			{ global },
		)

		cy.contains("button", "First: 0").click()
		cy.contains("button", "First: 1")
		cy.contains("button", "Second: 0").click()
		cy.contains("button", "Second: 5")
		cy.then(() => {
			expect(changes.first).to.have.been.calledOnceWith(1)
			expect(changes.second).to.have.been.calledOnceWith(5)
			expect(rootClicks.first).to.have.been.calledOnce
			expect(rootClicks.second).to.have.been.calledOnce
		})

		// a new prop value reaches the mounted instance, which keeps its state
		cy.then(() => (scope.firstTitle = "Renamed"))
		cy.contains("button", "Renamed: 1")

		// a block writes to a ref that the script returned
		cy.get("input").first().type("hello")
		cy.contains("button", "Renamed says hello")
		cy.contains("button", "Second says hello").should("not.exist")

		cy.then(() => (shown.value = false))
		cy.get("button").should("not.exist")
		cy.then(() => expect(unmounted).to.have.members(["Renamed", "Second"]))
	})

	it("renders after an async setup resolves", () => {
		let resolveSetup: (bindings: object) => void
		setComponent({
			setup: () => new Promise((resolve) => (resolveSetup = resolve)),
		})
		cy.mount(StudioComponentRenderer, {
			props: {
				studioComponent: counterBlock("async", { title: "Async" }),
				evaluationContext: {},
				listeners: {},
			},
			global,
		})

		cy.get("button").should("not.exist")
		cy.then(() => resolveSetup({ label: "Loaded", note: ref("") }))
		cy.contains("button", "Loaded")
	})

	it("keeps a component rendering with its saved inputs when its script is not valid", () => {
		const doc = { ...counterDoc(COMPONENT_ID), inputs: [{ input_name: "title", type: "text" }] }
		setComponent({ data: () => ({}) }, doc)
		cy.mount(StudioComponentRenderer, {
			props: {
				studioComponent: counterBlock("broken", { title: "Saved" }),
				evaluationContext: {},
				listeners: {},
			},
			global,
		})

		cy.contains("button", "Saved says")
		cy.then(() => {
			const store = useComponentStore()
			expect(store.componentScriptErrors.get(COMPONENT_ID)).to.include('cannot use "data"')
			expect(store.getComponentProps(COMPONENT_ID)).to.deep.equal(doc.inputs)
		})
	})

	it("accepts only a component definition", () => {
		expect(() => validateComponentScript(function setup() {})).to.throw("must export an object")
		expect(() => validateComponentScript({ props: {}, methods: {} })).to.throw('cannot use "methods"')
		expect(() => validateComponentScript({ setup: {} })).to.throw("setup")
		expect(validateComponentScript(counterScript)).to.equal(counterScript)
	})

	it("describes props for the form in the editor", () => {
		const inputs = getEditorProps({
			title: { type: String, required: true },
			step: { type: Number, default: 1 },
			open: Boolean,
			rows: { type: Array, default: () => [] },
			size: { type: String, default: "md", meta: { control: "select", options: ["sm", "md"] } },
		})
		expect(inputs.map((input) => [input.input_name, input.prop_type, input.type, input.default])).to.deep.equal([
			["title", "String", "text", undefined],
			["step", "Number", "number", "1"],
			["open", "Boolean", "checkbox", undefined],
			["rows", "Array", "code", undefined],
			["size", "String", "select", "md"],
		])
		expect(inputs[0].required).to.equal(1)
		expect(inputs[4].options).to.equal("sm\nmd")
		expect(getEditorProps(["title"])).to.deep.equal([{ input_name: "title", type: "text" }])
	})

	it("writes a prop from the form into the script, and leaves the rest of the script as written", () => {
		const title = { input_name: "title", type: "text", required: 1 }
		const size = { input_name: "size", type: "select", options: "sm\nmd", default: "md" }
		let script = setScriptProp("", null, title)
		expect(script).to.equal("export default {\n\tprops: {\n\t\ttitle: { type: String, required: true },\n\t},\n}\n")

		script = setScriptProp(script, null, size)
		expect(script).to.include('size: { type: String, default: "md", meta: { control: "select", options: ["sm","md"] } },')
		script = setScriptProp(script, title, { ...title, input_name: "heading", required: 0 })
		expect(script).to.include("\t\theading: String,\n").and.not.include("title")
		script = setScriptProp(script, size, null)
		expect(script).to.equal("export default {\n\tprops: {\n\t\theading: String,\n\t},\n}\n")
		expect(() => setScriptProp(script, null, { input_name: "heading", type: "text" })).to.throw("already exists")

		const written = [
			'import { ref } from "vue"',
			"",
			"// a counter",
			"export default {",
			"\tprops: { rows: { type: Array, default: () => [] }, open: Boolean },",
			"\tsetup() {",
			"\t\treturn { count: ref(0) }",
			"\t},",
			"}",
			"",
		].join("\n")
		const rows = { input_name: "rows", type: "code" }
		const edited = setScriptProp(written, rows, { ...rows, description: "The rows to show" })
		expect(edited).to.equal(
			written.replace(
				"rows: { type: Array, default: () => [] }",
				'rows: { type: Array, default: () => [], meta: { description: "The rows to show" } }',
			),
		)
		expect(setScriptProp(written, null, { input_name: "step", type: "number", default: "2" })).to.include(
			"open: Boolean, step: { type: Number, default: 2 } },",
		)
		expect(setScriptProp("export default {\n\tsetup() {},\n}\n", null, title)).to.equal(
			"export default {\n\tprops: {\n\t\ttitle: { type: String, required: true },\n\t},\n\tsetup() {},\n}\n",
		)
		expect(() => setScriptProp(written, null, { input_name: "bad", type: "code", default: "[1," })).to.throw(
			"not valid JavaScript",
		)

		// a number and a checkbox give their default as a number and a boolean
		const number = { input_name: "count", type: "number" }
		const checkbox = { input_name: "open", type: "checkbox" }
		const add = (input: Record<string, any>) => setScriptProp("", null, input as any)
		expect(add({ ...number, default: 5 })).to.include("count: { type: Number, default: 5 }")
		expect(add({ ...number, default: "" })).to.include("count: Number")
		expect(() => add({ ...number, default: "five" })).to.throw("must be a number")
		expect(add({ ...checkbox, default: true })).to.include("open: { type: Boolean, default: true }")
		expect(add({ ...checkbox, default: false })).to.include("open: Boolean")
		expect(() => add({ ...size, default: "lg" })).to.throw("one of the options")

		// the form gives the Vue type, and the control only when the user selected one
		expect(add({ input_name: "rows", type: "code", prop_type: "Array", control: "", default: "[]" })).to.include(
			"rows: { type: Array, default: () => ([]) }",
		)
		expect(add({ input_name: "note", type: "textarea", prop_type: "String", control: "textarea" })).to.include(
			'note: { type: String, meta: { control: "textarea" } }',
		)
		expect(add({ input_name: "name", type: "text", prop_type: "String", control: "text" })).to.include(
			'name: { type: String, meta: { control: "text" } }',
		)
		expect(add({ input_name: "name", type: "text", prop_type: "String", control: "" })).to.include("name: String")
		const mixed = "export default {\n\tprops: {\n\t\tid: { type: [String, Number], validator: () => true },\n\t},\n}\n"
		const id = getEditorProps({ id: { type: [String, Number] } })[0]
		expect([id.prop_type, id.type]).to.deep.equal(["String | Number", "text"])
		expect(setScriptProp(mixed, id, { ...id, required: 1 })).to.include("id: { type: [String, Number], required: true },")
		expect(setScriptProp(mixed, id, { ...id, prop_type: "Object", type: "code" })).to.include("id: Object,")

		// an unchanged default stays as the script has it
		const typed = "export default {\n\tprops: {\n\t\topen: { type: Boolean, default: false },\n\t},\n}\n"
		const previous = { ...checkbox, default: "false" }
		expect(setScriptProp(typed, previous, { ...checkbox, default: false, required: 1 } as any)).to.include(
			"open: { type: Boolean, required: true, default: false }",
		)
	})

	it("leaves props to the script when the form cannot change them safely", () => {
		expect(getPropsReadOnlyReason("")).to.equal("")
		expect(getPropsReadOnlyReason("export default { props: { title: String } }")).to.equal("")
		expect(getPropsReadOnlyReason("export default { props: { ...base, title: String } }")).to.include("another object")
		expect(getPropsReadOnlyReason('export default { props: ["title"] }')).to.include("as an object")
		expect(getPropsReadOnlyReason("export default { props: {")).to.include("syntax error")
		expect(getPropsReadOnlyReason("export default function setup() {}")).to.include("export an object")
	})
})
