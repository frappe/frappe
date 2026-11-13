import { pinia } from "../support/component"

import { setActivePinia } from "pinia"
import { computed, defineComponent, h, onUnmounted, reactive, ref } from "vue"

import StudioComponentRenderer from "@/components/StudioComponentRenderer.vue"
import { setComponentScriptImporters, unregisterStudioComponentScripts } from "@/data/studioComponentScripts"
import { registerGlobalComponents } from "@/globals"
import useComponentStore from "@/stores/componentStore"
import getBlockTemplate from "@/utils/blockTemplate"
import { getInputsFromProps, validateComponentScript, type ComponentScript } from "@/utils/componentScript"
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
				componentProps: { label: "{{ inputs.title }} says {{ note }}" },
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
							listeners: { change: changes[name] },
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
			expect(store.getComponentInputs(COMPONENT_ID)).to.deep.equal(doc.inputs)
		})
	})

	it("accepts only a component definition", () => {
		expect(() => validateComponentScript(function setup() {})).to.throw("must export an object")
		expect(() => validateComponentScript({ props: {}, methods: {} })).to.throw('cannot use "methods"')
		expect(() => validateComponentScript({ setup: {} })).to.throw("setup")
		expect(validateComponentScript(counterScript)).to.equal(counterScript)
	})

	it("describes props as inputs for the editor", () => {
		const inputs = getInputsFromProps({
			title: { type: String, required: true },
			step: { type: Number, default: 1 },
			open: Boolean,
			rows: { type: Array, default: () => [] },
			size: { type: String, default: "md", studio: { type: "select", options: ["sm", "md"] } },
		})
		expect(inputs.map((input) => [input.input_name, input.type, input.default])).to.deep.equal([
			["title", "text", undefined],
			["step", "number", "1"],
			["open", "checkbox", undefined],
			["rows", "code", undefined],
			["size", "select", "md"],
		])
		expect(inputs[0].required).to.equal(1)
		expect(inputs[4].options).to.equal("sm\nmd")
		expect(getInputsFromProps(["title"])).to.deep.equal([{ input_name: "title", type: "text" }])
	})
})
