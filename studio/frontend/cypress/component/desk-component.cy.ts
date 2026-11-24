import { pinia } from "../support/component"

import { setActivePinia } from "pinia"
import { defineComponent, h, ref } from "vue"

import "@/setupFrappeUIResource"
import DeskComponent from "@/desk/DeskComponent.vue"
import { registerGlobalComponents } from "@/globals"
import useComponentStore from "@/stores/componentStore"
import getBlockTemplate from "@/utils/blockTemplate"

const COMPONENT_ID = "cypress_desk_notice"
const API = { method: "GET", pathname: "/api/method/frappe.studio.desk.get_desk_component" }

// desk has no app, so the browser compiles the script that the component carries
const script = `import { computed } from "vue"

export default {
	props: {
		title: { type: String, default: "Notice" },
		count: { type: Number, default: 1, meta: { description: "How many" } },
	},
	setup(props) {
		const label = computed(() => props.title + " x" + props.count)
		return { label }
	},
}
`

const componentDoc = {
	name: COMPONENT_ID,
	component_id: COMPONENT_ID,
	component_name: "Desk Notice",
	script,
	inputs: [],
	block: JSON.stringify({
		...getBlockTemplate("container"),
		componentId: `${COMPONENT_ID}-root`,
		children: [
			{ componentName: "Button", componentId: `${COMPONENT_ID}-label`, componentProps: { label: "{{ label }}" } },
		],
	}),
}

const global = { plugins: [pinia, { install: registerGlobalComponents }] }

describe("a global component on desk", () => {
	beforeEach(() => setActivePinia(pinia))
	afterEach(() => useComponentStore().removeCachedComponent(COMPONENT_ID))

	it("renders with the host's props and reports the props that it declares", () => {
		cy.intercept(API, { message: [componentDoc] })
		const props = ref<Record<string, any>>({ title: "Release" })
		const onLoad = cy.stub()
		cy.mount(
			defineComponent({
				setup: () => () => h(DeskComponent, { component: COMPONENT_ID, props: props.value, onLoad }),
			}),
			{ global },
		)

		cy.contains("button", "Release x1")
		cy.then(() => {
			const definition = onLoad.firstCall.args[0]
			expect(definition.component_name).to.equal("Desk Notice")
			expect(definition.props.map((prop: any) => [prop.input_name, prop.type, prop.default])).to.deep.equal([
				["title", "text", "Notice"],
				["count", "number", "1"],
			])
			props.value = { title: "Release", count: 3 }
		})
		cy.contains("button", "Release x3")
	})

	it("draws the root component of a workspace", () => {
		const root = { ...componentDoc, name: "workspace_sales", component_id: "workspace_sales", script: null }
		root.block = JSON.stringify({
			...getBlockTemplate("container"),
			componentId: "workspace-root",
			children: [
				{
					componentName: COMPONENT_ID,
					componentId: "widget",
					isStudioComponent: true,
					componentProps: { title: "Orders", count: 2 },
				},
			],
		})
		cy.intercept(
			{ method: "GET", pathname: "/api/method/frappe.desk.workspace_component.get_workspace_component" },
			{ message: [root, componentDoc] },
		)
		cy.mount(DeskComponent, { props: { workspace: "Sales" }, global })
		cy.contains("button", "Orders x2")
		cy.then(() => useComponentStore().removeCachedComponent("workspace_sales"))
	})

	it("says so when the component is gone", () => {
		cy.intercept(API, { statusCode: 404, body: { exc_type: "DoesNotExistError" } })
		cy.mount(DeskComponent, { props: { component: COMPONENT_ID }, global })
		cy.contains(`Component ${COMPONENT_ID} was not found.`)
	})
})
