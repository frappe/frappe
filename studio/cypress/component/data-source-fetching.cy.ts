import { pinia } from "../support/component"

import { setActivePinia } from "pinia"
import { nextTick } from "vue"

import "@/setupFrappeUIResource"
import useCodeStore from "@/stores/codeStore"
import type { Resource } from "@/types/Studio/StudioResource"
import type { StudioPage } from "@/types/Studio/StudioPage"
import type { Variable } from "@/types/Studio/StudioPageVariable"

// Assertions only rely on the Administrator and Guest users every site has
const page = { name: "page-1" } as StudioPage
const ADMINISTRATOR = { name: "Administrator", full_name: "Administrator" }

// a saved Studio Page Resource row: JSON columns come back as strings
function listResource(overrides: Record<string, any> = {}): Resource {
	return {
		resource_name: "users",
		resource_type: "Document List",
		document_type: "User",
		fields: JSON.stringify(["name", "full_name"]),
		filters: JSON.stringify({ name: "Administrator" }),
		limit: 5,
		sort_field: "",
		sort_order: "",
		auto: true,
		...overrides,
	} as Resource
}

function documentResource(overrides: Record<string, any>): Resource {
	return {
		resource_name: "user",
		resource_type: "Document",
		document_type: "User",
		auto: true,
		...overrides,
	} as Resource
}

function variable(variable_name: string, variable_type: string, initial_value: any): Variable {
	return { name: variable_name, variable_name, variable_type, initial_value }
}

async function loadPage(resources: Resource[], variables: Variable[] = []) {
	const codeStore = useCodeStore()
	await codeStore.setPageVariables(page, variables)
	await codeStore.setPageResources(page, false, resources)
	return codeStore
}

const waitForResponse = (alias: string) =>
	cy.wait(alias).then((interception) => {
		expect(interception.response?.statusCode).to.equal(200)
		return interception
	})
const requestBody = (alias: string) => waitForResponse(alias).its("request.body")
const requestQuery = (alias: string) => waitForResponse(alias).its("request.query")

describe("data source fetching", () => {
	beforeEach(() => {
		setActivePinia(pinia)
		cy.login()
		cy.intercept("/api/method/frappe.client.get_list*").as("getList")
		cy.intercept(/\/api\/method\/frappe\.client\.get(\?|$)/).as("getDoc")
		cy.intercept("/api/method/frappe.client.get_value*").as("getValue")
	})

	afterEach(() => useCodeStore().teardownPage())

	describe("Document List", () => {
		it("fetches the saved fields, filters, sort and limit", () => {
			cy.wrap(loadPage([listResource({ sort_field: "creation", sort_order: "DESC" })]))

			requestBody("@getList").should((body) => {
				expect(body.doctype).to.equal("User")
				expect(body.fields).to.deep.equal(["name", "full_name"])
				expect(body.filters).to.deep.equal({ name: "Administrator" })
				expect(body.order_by).to.equal("creation DESC")
				expect(body.limit).to.equal(5)
			})
		})

		it("exposes the fetched rows on the resource", () => {
			cy.wrap(loadPage([listResource()])).then((codeStore: any) => {
				waitForResponse("@getList")
				cy.wrap(codeStore.resources).its("users.data").should("deep.equal", [ADMINISTRATOR])
			})
		})

		it("fetches all fields when none are saved", () => {
			cy.wrap(loadPage([listResource({ fields: "[]" })])).then((codeStore: any) => {
				requestBody("@getList").its("fields").should("equal", "*")
				cy.wrap(codeStore.resources)
					.its("users.data.0")
					.should("include.keys", ["name", "email", "user_type"])
			})
		})

		it("does not fetch until asked when auto fetch is off", () => {
			cy.wrap(loadPage([listResource({ auto: false })])).then((codeStore: any) => {
				cy.get("@getList.all").should("have.length", 0)
				cy.then(() => codeStore.resources.users.reload())
				waitForResponse("@getList")
				cy.wrap(codeStore.resources).its("users.data").should("deep.equal", [ADMINISTRATOR])
			})
		})

		it("runs the transform on fetched rows", () => {
			const transform = "function transform(data) { return data.map((user) => user.full_name.toUpperCase()) }"
			cy.wrap(loadPage([listResource({ transform })])).then((codeStore: any) => {
				waitForResponse("@getList")
				cy.wrap(codeStore.resources).its("users.data").should("deep.equal", ["ADMINISTRATOR"])
			})
		})

		it("evaluates dynamic filters and refetches when a variable changes", () => {
			const filters = JSON.stringify({
				name: ["in", ["Administrator", "Guest"]],
				user_type: "{{ userType }}",
			})
			const variables = [variable("userType", "String", '"System User"')]

			cy.wrap(loadPage([listResource({ filters })], variables)).then((codeStore: any) => {
				requestBody("@getList").its("filters.user_type").should("equal", "System User")
				cy.wrap(codeStore.resources).its("users.data").should("deep.equal", [ADMINISTRATOR])

				cy.then(() => {
					codeStore.variables.userType = "Website User"
					return nextTick()
				})
				requestBody("@getList").its("filters.user_type").should("equal", "Website User")
				cy.wrap(codeStore.resources)
					.its("users.data")
					.should("deep.equal", [{ name: "Guest", full_name: "Guest" }])
			})
		})

		it("drops a dynamic filter whose value is empty", () => {
			const filters = JSON.stringify({ name: "Administrator", user_type: "{{ userType }}" })
			cy.wrap(loadPage([listResource({ filters })], [variable("userType", "Object", "null")]))
			requestBody("@getList").its("filters").should("deep.equal", { name: "Administrator" })
		})
	})

	describe("API Resource", () => {
		it("calls the method with evaluated params", () => {
			cy.intercept("/api/method/frappe.client.get_count*").as("getCount")
			const resource = {
				resource_name: "userCount",
				resource_type: "API Resource",
				url: "/api/method/frappe.client.get_count",
				method: "POST",
				params: JSON.stringify({ doctype: "User", filters: { name: "{{ userId }}" } }),
				auto: true,
			} as Resource

			cy.wrap(loadPage([resource], [variable("userId", "String", '"Administrator"')])).then(
				(codeStore: any) => {
					requestBody("@getCount").should("deep.equal", {
						doctype: "User",
						filters: { name: "Administrator" },
					})
					cy.wrap(codeStore.resources).its("userCount.data").should("equal", 1)
				},
			)
		})
	})

	describe("Document", () => {
		it("fetches the saved document", () => {
			cy.wrap(loadPage([documentResource({ document_name: "Administrator" })])).then((codeStore: any) => {
				requestQuery("@getDoc").should("deep.include", { doctype: "User", name: "Administrator" })
				cy.wrap(codeStore.resources).its("user.doc.user_type").should("equal", "System User")
			})
		})

		it("uses a name filter as the document name without a lookup", () => {
			const resource = documentResource({
				fetch_document_using_filters: true,
				filters: JSON.stringify({ name: "{{ userId }}" }),
			})

			cy.wrap(loadPage([resource], [variable("userId", "String", '"Guest"')])).then((codeStore: any) => {
				requestQuery("@getDoc").its("name").should("equal", "Guest")
				cy.wrap(codeStore.resources).its("user.doc.user_type").should("equal", "Website User")
				cy.get("@getValue.all").should("have.length", 0)
			})
		})

		it("looks up the document name from other filters", () => {
			const resource = documentResource({
				fetch_document_using_filters: true,
				filters: JSON.stringify({ first_name: "Guest" }),
			})

			cy.wrap(loadPage([resource]))
			requestBody("@getValue").should("deep.include", { doctype: "User", filters: { first_name: "Guest" } })
			requestQuery("@getDoc").its("name").should("equal", "Guest")
		})

		it("leaves the resource empty when no document matches the filters", () => {
			const resource = documentResource({
				fetch_document_using_filters: true,
				filters: JSON.stringify({ first_name: "No Such User" }),
			})

			cy.wrap(loadPage([resource])).then((codeStore: any) => {
				waitForResponse("@getValue")
				cy.wrap(codeStore.resources).should("have.property", "user", undefined)
			})
		})
	})
})
