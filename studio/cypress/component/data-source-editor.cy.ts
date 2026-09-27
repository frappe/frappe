import { pinia } from "../support/component"

import { setActivePinia } from "pinia"
// @ts-ignore
import { resourcesPlugin } from "frappe-ui"

import "@/setupFrappeUIResource"
import DataPanel from "@/components/DataPanel.vue"
import ResourceDialog from "@/components/ResourceDialog.vue"
import useStudioStore from "@/stores/studioStore"
import useCodeStore from "@/stores/codeStore"
import type { StudioPage } from "@/types/Studio/StudioPage"

const APP_NAME = "cypress-data-sources"

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
	})

	after(() => {
		cy.login()
		cy.remove_doc("Studio App", APP_NAME, true)
	})

	beforeEach(() => {
		setActivePinia(pinia)
		cy.login()
		cy.intercept("/api/method/studio.api.get_doctype_fields*").as("getDocTypeFields")
		cy.intercept("/api/method/studio.api.get_sort_fields*").as("getSortFields")
		cy.intercept("/api/method/studio.api.get_whitelisted_methods*").as("getWhitelistedMethods")
		// pages stay until after(): a data source from an earlier test may still refetch its page
		cy.insert_doc("Studio App", { app_name: APP_NAME, app_title: "Cypress Data Sources" }, true)
		cy.insert_doc("Studio Page", { studio_app: APP_NAME }).then((createdPage) => {
			page = createdPage
			saveUserList("users", ["email", "full_name"])
			// a Document data source for a doctype with known whitelisted methods
			saveDataSource({
				resource_name: "currentPage",
				resource_type: "Document",
				document_type: "Studio Page",
				document_name: page.name,
				whitelisted_methods: JSON.stringify(["publish"]),
			})
		})
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

		it("asks for fields on a Document List", () => {
			openNewDataSource()
			field("Data Source Name").type("admins")
			chooseDocType("User")
			submit("Add")
			cy.contains("Please set Fields").should("be.visible")
		})

		it("asks for filters on a Document fetched using filters", () => {
			openNewDataSource()
			field("Data Source Name").type("admin")
			chooseOption("Type", "Document")
			chooseDocType("User")
			cy.get("[role='dialog']").contains("Dynamically fetch document using filters").click()
			submit("Add")
			cy.contains("Please set Filters").should("be.visible")
		})

		it("saves a new Document List to the page", () => {
			openNewDataSource()
			field("Data Source Name").type("admins")
			chooseDocType("User")
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

		it("opens when mounted with a data source already set", () => {
			savedDataSource("users").then((resource) => {
				cy.mount(ResourceDialog, {
					props: { showDialog: true, resource: { ...resource, resource_id: resource.name } },
					global: { plugins: [pinia, resourcesPlugin] },
				})
			})
			field("Data Source Name").should("have.value", "users")
			field("Fields").should("contain.text", "email, full_name")
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

	// these data sources aren't fetched (auto 0): the server rejects a query for fields the doctype no longer has
	describe("fields removed from the doctype", () => {
		it("warns about the missing field and keeps it out of the summary", () => {
			saveUserList("staleUsers", ["email", "deleted_field", "full_name"], 0)
			openDataSource("staleUsers")

			cy.contains("deleted_field is no longer a field on User.").should("be.visible")
			field("Fields").should("contain.text", "email, full_name").and("not.contain.text", "deleted_field")

			field("Fields").click()
			option("deleted_field").should("contain.text", "Missing Field")
			option("email").should("not.contain.text", "Missing Field")
		})

		it("pluralises the warning for several missing fields", () => {
			saveUserList("staleUsers", ["email", "deleted_field", "another_deleted_field"], 0)
			openDataSource("staleUsers")
			cy.contains("deleted_field, another_deleted_field are no longer fields on User.").should("be.visible")
		})

		it("removes missing fields and saves only the valid ones", () => {
			saveUserList("staleUsers", ["email", "deleted_field", "full_name"], 0)
			openDataSource("staleUsers")
			cy.get("[role='dialog']").contains("button", "Remove").click()
			cy.contains("no longer a field").should("not.exist")
			submit("Save")

			savedFields("staleUsers").should("deep.equal", ["email", "full_name"])
		})
	})

	// saved straight to the site, bypassing the editor, like a data source saved before its fields were removed
	function saveDataSource(resource: Record<string, any>) {
		cy.call("frappe.client.insert", {
			doc: {
				doctype: "Studio Page Resource",
				parent: page.name,
				parenttype: "Studio Page",
				parentfield: "resources",
				...resource,
			},
		})
	}

	function saveUserList(resource_name: string, fields: string[], auto = 1) {
		saveDataSource({
			auto,
			resource_name,
			resource_type: "Document List",
			document_type: "User",
			fields: JSON.stringify(fields),
			filters: JSON.stringify({ name: "Administrator" }),
			limit: 5,
		})
	}

	function mountDataPanel() {
		// after the test's queued saves, so the panel loads the data sources they added
		cy.then(() => {
			useStudioStore().activePage = page
			return useCodeStore().setPageResources(page, true)
		})
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

// the input/trigger a FormControl label points at
const field = (label: string) =>
	cy
		.get("[role='dialog']")
		.contains("label", new RegExp(`^\\s*${label}`))
		.invoke("attr", "for")
		.then((id) => cy.get(`[id="${id}"]`))
const chooseOption = (label: string, option: string) => {
	field(label).click()
	cy.get("[role='option']")
		.contains(new RegExp(`^${option}$`))
		.click()
}
const chooseDocType = (doctype: string) => {
	field("Document Type").type(doctype)
	// the option's label, not its description (the doctype's module)
	cy.get("[role='option']")
		.contains(new RegExp(`^${doctype}$`))
		.click()
	cy.wait("@getDocTypeFields")
}
const option = (label: string) => cy.get("[role='option']").contains(label).closest("[role='option']")
const submit = (label: "Add" | "Save") =>
	cy
		.get("[role='dialog']")
		.contains("button", new RegExp(`^${label}$`))
		.click()
