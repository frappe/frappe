import { pinia } from "../support/component"

import { setActivePinia } from "pinia"
// @ts-ignore
import { resourcesPlugin } from "frappe-ui"

import "@/setupFrappeUIResource"
import DataPanel from "@/components/DataPanel.vue"
import useStudioStore from "@/stores/studioStore"
import useCodeStore from "@/stores/codeStore"
import type { StudioPage } from "@/types/Studio/StudioPage"

// User fields a saved data source still selects after they were removed from the doctype
const REMOVED_FIELDS = ["deleted_field", "another_deleted_field"]
const APP_NAME = `cypress-data-sources-${Date.now()}`

// Neither comes from the editor: the popovers' ResizeObserver loop, and the Document Type Link's
// debounced search landing between tests, after that test's session is gone
const IGNORED_ERRORS = ["ResizeObserver loop", "frappe.desk.search.search_link"]

// Data sources are edited the way the builder does it: DataPanel reads the page's saved rows from
// the site, opens them in ResourceDialog and writes the changes back
describe("data source editor", () => {
	let page: StudioPage

	before(() => {
		Cypress.on(
			"uncaught:exception",
			(error) => !IGNORED_ERRORS.some((message) => error.message.includes(message)),
		)
		cy.login()
		cy.insert_doc("Studio App", { app_name: APP_NAME, app_title: "Cypress Data Sources" })
	})

	after(() => {
		cy.login()
		cy.remove_doc("Studio App", APP_NAME)
	})

	beforeEach(() => {
		setActivePinia(pinia)
		cy.login()
		cy.intercept("/api/method/studio.api.get_doctype_fields*").as("getDocTypeFields")
		cy.intercept("/api/method/studio.api.get_sort_fields*").as("getSortFields")
		cy.intercept("/api/method/studio.api.get_whitelisted_methods*").as("getWhitelistedMethods")
		createPage().then((createdPage) => (page = createdPage))
	})

	describe("adding", () => {
		it("asks for the data source name and doctype", () => {
			openNewDataSource()
			submit("Add")
			cy.contains("Please set Data Source Name, Document Type").should("be.visible")
		})

		it("asks for URL on an API resource", () => {
			openNewDataSource()
			field("Data Source Name").type("stats")
			chooseOption("Type", "API Resource")
			submit("Add")
			cy.contains("Please set URL").should("be.visible")
		})

		it("saves a new Document List to the page", () => {
			openNewDataSource()
			field("Data Source Name").type("admins")
			field("Document Type").type("User")
			cy.contains("[role='option']", /^\s*User\s*$/).click()
			cy.wait("@getDocTypeFields")
			field("Fields").click()
			option("email").click()
			cy.get("body").type("{esc}")
			submit("Add")

			savedDataSource("admins").should((resource) => {
				expect(resource.resource_type).to.equal("Document List")
				expect(resource.document_type).to.equal("User")
				expect(JSON.parse(resource.fields)).to.deep.equal(["email"])
			})
		})
	})

	describe("doctype metadata from the server", () => {
		it("offers the doctype's fields along with standard fields", () => {
			openDataSource("users")
			field("Fields").click()
			for (const fieldname of ["email", "full_name", "user_type", "name", "owner", "idx", "docstatus"]) {
				option(fieldname).should("exist")
			}
		})

		it("offers the doctype's labelled fields for sorting", () => {
			openDataSource("users")
			cy.wait("@getSortFields")
			field("Sort Field").click()
			option("Full Name").should("exist")
			option("Email").should("exist")
		})

		it("offers the document's whitelisted methods", () => {
			openDataSource("currentPage")
			cy.wait("@getWhitelistedMethods").its("request.body").should("deep.equal", { doctype: "Studio Page" })
			field("Whitelisted Methods").should("contain.text", "publish").click()
			option("unpublish").should("exist")
			option("save_draft").should("exist")
		})
	})

	describe("editing", () => {
		it("opens a saved data source with its saved config", () => {
			openDataSource("users")
			field("Data Source Name").should("have.value", "users")
			field("Fields").should("contain.text", "email, full_name")
			field("Limit").should("have.value", "5")
			cy.contains("no longer a field").should("not.exist")
		})

		it("saves edits back to the page", () => {
			openDataSource("users")
			field("Fields").click()
			option("user_type").click()
			cy.get("body").type("{esc}")
			submit("Save")

			savedFields("users").should("deep.equal", ["email", "full_name", "user_type"])
		})
	})

	describe("fields removed from the doctype", () => {
		it("warns about the missing field and keeps it out of the summary", () => {
			openDataSource("staleUsers")

			cy.contains(`${REMOVED_FIELDS[0]} is no longer a field on User.`).should("be.visible")
			field("Fields").should("contain.text", "email, full_name").and("not.contain.text", REMOVED_FIELDS[0])

			field("Fields").click()
			option(REMOVED_FIELDS[0]).should("contain.text", "Missing Field")
			option("email").should("not.contain.text", "Missing Field")
		})

		it("pluralises the warning for several missing fields", () => {
			openDataSource("veryStaleUsers")
			cy.contains(`${REMOVED_FIELDS.join(", ")} are no longer fields on User.`).should("be.visible")
		})

		it("removes missing fields and saves only the valid ones", () => {
			openDataSource("staleUsers")
			cy.get("[role='dialog']").contains("button", "Remove").click()
			cy.contains("no longer a field").should("not.exist")
			submit("Save")

			savedFields("staleUsers").should("deep.equal", ["email", "full_name"])
		})
	})

	function mountDataPanel() {
		useStudioStore().activePage = page
		cy.wrap(useCodeStore().setPageResources(page, true))
		cy.mount(DataPanel, { global: { plugins: [pinia, resourcesPlugin] } })
	}

	function openNewDataSource() {
		mountDataPanel()
		cy.contains("button", "Add Data Source").click()
	}

	function openDataSource(resourceName: string) {
		mountDataPanel()
		cy.contains(new RegExp(`^${resourceName}$`))
			.closest(".group\\/item")
			.find(".lucide-pencil")
			.parent()
			.click({ force: true })
		cy.wait("@getDocTypeFields")
	}

	function savedDataSource(resourceName: string) {
		return cy
			.get_doc("Studio Page", page.name)
			.then(({ data }) => data.resources.find((row: any) => row.resource_name === resourceName))
	}

	function savedFields(resourceName: string) {
		return savedDataSource(resourceName).then((resource) => JSON.parse(resource.fields))
	}
})

function createPage() {
	const userList = (resource_name: string, fields: string[]) => ({
		resource_name,
		resource_type: "Document List",
		document_type: "User",
		fields: JSON.stringify(fields),
		filters: JSON.stringify({ name: "Administrator" }),
		limit: 5,
	})
	return cy
		.insert_doc("Studio Page", {
			studio_app: APP_NAME,
			resources: [
				userList("users", ["email", "full_name"]),
				userList("staleUsers", ["email", REMOVED_FIELDS[0], "full_name"]),
				userList("veryStaleUsers", ["email", ...REMOVED_FIELDS]),
			],
		})
		.then((createdPage) => addCurrentPageDataSource(createdPage))
}

// a Document data source on the page itself, for a doctype with known whitelisted methods
function addCurrentPageDataSource(createdPage: StudioPage) {
	return cy.update_doc("Studio Page", createdPage.name, {
		resources: [
			...(createdPage as any).resources,
			{
				resource_name: "currentPage",
				resource_type: "Document",
				document_type: "Studio Page",
				document_name: createdPage.name,
				whitelisted_methods: JSON.stringify(["publish"]),
			},
		],
	})
}

// the input/trigger a FormControl label points at
const field = (label: string) =>
	cy
		.get("[role='dialog']")
		.contains("label", new RegExp(`^\\s*${label}`))
		.invoke("attr", "for")
		.then((id) => cy.get(`[id="${id}"]`))
const chooseOption = (label: string, option: string) => {
	field(label).click()
	cy.get("[role='option']").contains(option).click()
}
const option = (label: string) => cy.get("[role='option']").contains(label).closest("[role='option']")
const submit = (label: "Add" | "Save") =>
	cy
		.get("[role='dialog']")
		.contains("button", new RegExp(`^${label}$`))
		.click()
