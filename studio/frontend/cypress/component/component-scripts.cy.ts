import { pinia } from "../support/component"

import { setActivePinia } from "pinia"
import { computed, defineComponent, h, onUnmounted, reactive, ref } from "vue"

import AppComponent from "@/runtime/components/AppComponent.vue"
import StudioComponentRenderer from "@/runtime/components/StudioComponentRenderer.vue"
import { setComponentScriptImporters, unregisterStudioComponentScripts } from "@/runtime/data/studioComponentScripts"
import { registerGlobalComponents } from "@/runtime/globals"
import useComponentStore from "@/runtime/stores/componentStore"
import getBlockTemplate from "@/utils/blockTemplate"
import { getEditorProps, validateComponentScript, type ComponentScript } from "@/runtime/utils/componentScript"
import { getPropReadOnlyReason, getPropsReadOnlyReason, setScriptProp } from "@/utils/componentScriptProps"
import { getBlockInstance } from "@/runtime/utils/serializer"

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

	it("shows a component that cannot be fetched as missing, in the preview only", () => {
		const missingId = "cypress_missing"
		const mountMissing = (isPreview: boolean) => {
			;(window as any).is_preview = isPreview
			const block = getBlockInstance({ componentName: missingId, componentId: "missing-1", isStudioComponent: true })
			cy.mount(
				defineComponent({ setup: () => () => h(AppComponent, { block }) }),
				{ global },
			)
		}
		cy.intercept("POST", "**/api/method/frappe.studio.api.get_studio_component", { statusCode: 404 }).as(
			"getComponent",
		)
		cy.then(() => mountMissing(true))
		cy.wait("@getComponent")
		cy.contains(`Component Missing: ${missingId}`)

		cy.then(() => mountMissing(false))
		cy.contains("Component Missing").should("not.exist")
		cy.then(() => {
			delete (window as any).is_preview
			useComponentStore().removeCachedComponent(missingId)
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

	// a prop as the form gives it: the Vue type, the control in use, and the control that the user selected
	function prop(name: string, propType: string, fields: Record<string, any> = {}) {
		const controls: Record<string, string> = { String: "text", Number: "number", Boolean: "checkbox" }
		const type = fields.control || controls[propType] || "code"
		return { input_name: name, prop_type: propType, type, control: "", ...fields }
	}
	const script = (props: string) => `export default {\n\tprops: {\n\t\t${props},\n\t},\n}\n`

	it("writes a new prop into the script, and removes one", () => {
		const title = prop("title", "String", { required: 1 })
		const size = prop("size", "String", { control: "select", options: "sm\nmd", default: "md" })
		let source = setScriptProp("", null, title)
		expect(source).to.equal(script("title: { type: String, required: true }"))
		source = setScriptProp(source, null, size)
		expect(source).to.include('size: { type: String, default: "md", meta: { control: "select", options: ["sm","md"] } },')
		expect(() => setScriptProp(source, null, prop("title", "String"))).to.throw("already exists")
		expect(setScriptProp(source, size, null)).to.equal(script("title: { type: String, required: true }"))

		// the props stay on one line, or on a line each, as the script has them
		const written = 'import { ref } from "vue"\n\n// a counter\nexport default {\n\tprops: { rows: Array, open: Boolean },\n\tsetup() {},\n}\n'
		expect(setScriptProp(written, null, prop("step", "Number", { default: 2 }))).to.equal(
			written.replace("open: Boolean }", "open: Boolean, step: { type: Number, default: 2 } }"),
		)
		expect(setScriptProp(written, prop("open", "Boolean"), null)).to.equal(written.replace(", open: Boolean", ""))
		expect(setScriptProp("export default {\n\tsetup() {},\n}\n", null, title)).to.include("\tprops: {\n\t\ttitle:")

		const add = (name: string, propType: string, fields = {}) => setScriptProp("", null, prop(name, propType, fields))
		expect(add("count", "Number")).to.include("count: Number,")
		expect(add("open", "Boolean", { default: true })).to.include("open: { type: Boolean, default: true }")
		expect(add("open", "Boolean", { default: false })).to.include("open: Boolean,")
		expect(add("rows", "Array", { default: "[]" })).to.include("rows: { type: Array, default: () => ([]) }")
		expect(add("item", "Any")).to.include("item: null,")
		expect(add("data-id", "String", { control: "text" })).to.include('"data-id": { type: String, meta: { control: "text" } }')
		expect(() => add("count", "Number", { default: "five" })).to.throw("must be a number")
		expect(() => add("size", "String", { ...size, default: "lg" })).to.throw("one of the options")
		expect(() => add("rows", "Array", { default: "[1," })).to.throw("not valid JavaScript")
	})

	it("changes only the keys of a prop that the form changed", () => {
		// `props` is what the entry is at runtime, which the form reads
		const change = (entry: string, props: Record<string, any>, fields: Record<string, any>) => {
			const previous = getEditorProps(props)[0]
			return setScriptProp(script(entry), previous, { ...previous, ...fields })
		}
		const checked = "score: { type: Number, validator: (value) => value > 0 }"
		const score = { score: { type: Number, validator: () => true } }
		expect(change(checked, score, { required: 1 })).to.equal(script(checked.replace(" }", ", required: true }")))
		expect(change(checked, score, { input_name: "points" })).to.equal(script(checked.replace("score", "points")))

		// a type and a default that the form cannot show stay as written
		const typed = "rows: { type: Array as PropType<Row[]>, default: () => [] }"
		expect(change(typed, { rows: { type: Array, default: () => [] } }, { description: "The rows" })).to.equal(
			script(typed.replace(" }", ', meta: { description: "The rows" } }')),
		)
		const id = { id: [String, Number] }
		expect(change("id: [String, Number]", id, { required: 1 })).to.include(
			"id: { type: [String, Number], required: true },",
		)
		expect(change("id: [String, Number]", id, { prop_type: "Object", type: "code" })).to.include("id: Object,")
		expect(
			change("open: { type: Boolean, default: false }", { open: { type: Boolean, default: false } }, { required: 1 }),
		).to.include("open: { type: Boolean, default: false, required: true }")

		// a new type removes the default, also one that the form does not show
		expect(
			change(typed, { rows: { type: Array, default: () => [] } }, { prop_type: "String", type: "text" }),
		).to.equal(script("rows: { type: String }"))

		const title = { title: { type: String, required: true } }
		expect(change("title: { type: String, required: true }", title, { required: 0 })).to.equal(
			script("title: { type: String }"),
		)
		const size = { size: { type: String, default: "md" } }
		expect(change('size: { type: String, default: "md" }', size, { default: "lg" })).to.include('default: "lg" }')
		const color = { size: { type: String, meta: { control: "color" } } }
		expect(
			change('size: { type: String, meta: { control: "color" } }', color, { control: "", type: "text" }),
		).to.equal(script("size: { type: String }"))

		// a variable, a spread or a computed key can set a key that the form removes
		const refused = ["score: scoreOptions", "score: { type: Number, ...checks }", 'score: { type: Number, ["required"]: true }']
		for (const entry of refused) {
			expect(getPropReadOnlyReason(script(entry), "score")).to.include("advanced prop options")
		}
		const number = prop("score", "Number")
		expect(() => setScriptProp(script(refused[0]), number, { ...number, required: 1 })).to.throw("advanced prop options")
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
