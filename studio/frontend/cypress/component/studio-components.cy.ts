import { pinia } from "../support/component"

import { setActivePinia } from "pinia"
import { createMemoryHistory, createRouter } from "vue-router"
// @ts-ignore
import { resourcesPlugin } from "frappe-ui"

import "@/setupFrappeUIResource"
import AppPage from "@/pages/AppPage.vue"
import { registerGlobalComponents } from "@/globals"
import { loadPage } from "@/page/pageLoader"
import useComponentStore from "@/stores/componentStore"
import getBlockTemplate from "@/utils/blockTemplate"

const APP_NAME = "cypress-guest"
const COMPONENT_ID = "cypress_header"
const GET_COMPONENT = /\/api\/method\/frappe\.client\.get\?/

const headerBlock = {
	...getBlockTemplate("container"),
	componentId: "header-root",
	children: [
		{
			componentName: "Button",
			componentId: "header-button",
			componentProps: { label: "Hello from the header" },
		},
		{
			componentName: "Button",
			componentId: "header-subject",
			componentProps: { label: "{{ inputs.title }}" },
		},
	],
}
const pageBlocks = [
	{
		...getBlockTemplate("body"),
		children: [
			{
				componentName: COMPONENT_ID,
				componentId: "header-1",
				isStudioComponent: true,
				componentProps: { title: "{{ subject }}" },
			},
		],
	},
]

describe("studio components for guests", () => {
	let pageName: string

	before(() => {
		cy.login()
		cy.remove_doc("Studio App", APP_NAME, true)
		cy.remove_doc("Studio Component", COMPONENT_ID, true)
		cy.insert_doc("Studio Component", {
			component_id: COMPONENT_ID,
			component_name: "Cypress Header",
			block: JSON.stringify(headerBlock),
			// two inputs, so values would get a second evaluation pass if evaluation ran per input
			inputs: [
				{ input_name: "title", type: "string" },
				{ input_name: "subtitle", type: "string", default: "'sub'" },
			],
		})
		cy.insert_doc("Studio App", { app_name: APP_NAME, app_title: "Cypress Guest" })
		cy.insert_doc("Studio Page", {
			studio_app: APP_NAME,
			page_title: "Home",
			route: "/",
			blocks: JSON.stringify(pageBlocks),
			variables: [
				{
					variable_name: "subject",
					variable_type: "String",
					initial_value: JSON.stringify("E2E {{ 7 * 7 }}"),
				},
			],
			published: 1,
			allow_guest: 1,
		}).then((page) => (pageName = page.name))
	})

	after(() => {
		cy.login()
		cy.remove_doc("Studio App", APP_NAME, true)
		cy.remove_doc("Studio Component", COMPONENT_ID, true)
	})

	beforeEach(() => {
		setActivePinia(pinia)
		useComponentStore().removeCachedComponent(COMPONENT_ID)
		// a refused fetch also rejects frappe-ui's own auto fetch, outside the store's catch
		cy.on("uncaught:exception", (error) => !error.message.includes("frappe.client.get"))
		cy.asGuest()
		cy.intercept("GET", GET_COMPONENT).as("getComponent")
	})

	function mountAppPage() {
		window.app_name = APP_NAME
		const router = createRouter({
			history: createMemoryHistory(),
			routes: [{ path: "/", component: AppPage, meta: { pageName } }],
		})
		cy.then(() => router.push("/"))
		cy.then(() => loadPage(router, router.currentRoute.value, { meta: {}, fullPath: "" } as any))
		cy.mount(AppPage, {
			global: { plugins: [pinia, resourcesPlugin, router, { install: registerGlobalComponents }] },
		})
	}

	it("renders them on a published guest page although the guest cannot read them", () => {
		cy.request({
			url: `/api/method/frappe.client.get?doctype=Studio Component&name=${COMPONENT_ID}`,
			failOnStatusCode: false,
		})
			.its("status")
			.should("eq", 403)

		mountAppPage()

		cy.contains("button", "Hello from the header").should("be.visible")
		cy.get("@getComponent.all").should("have.length", 0)
	})

	it("evaluates an input value once, so text that looks like an expression stays text", () => {
		mountAppPage()

		cy.contains("button", "E2E {{ 7 * 7 }}").should("be.visible")
		cy.contains("button", "E2E 49").should("not.exist")
	})

	it("keeps a component from the page payload when a fetch of it is refused later", () => {
		cy.intercept("GET", GET_COMPONENT, (request) =>
			request.continue((response) => {
				response.setDelay(100)
			}),
		).as("getComponent")
		const store = useComponentStore()
		let header: Record<string, any>
		cy.login().then(() => cy.get_doc("Studio Component", COMPONENT_ID).then((doc) => (header = doc.data)))
		cy.asGuest()

		cy.then(() => {
			const fetching = store.loadComponent(COMPONENT_ID)
			store.setComponents([header as any])
			return fetching
		})
		cy.wait("@getComponent").its("response.statusCode").should("eq", 403)
		cy.then(() => expect(store.componentMap.get(COMPONENT_ID)?.componentName).to.equal("container"))
	})
})
