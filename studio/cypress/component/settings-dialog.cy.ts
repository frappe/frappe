import { pinia } from "../support/component"

import { setActivePinia } from "pinia"
// @ts-ignore
import { resourcesPlugin } from "frappe-ui"

import "@/setupFrappeUIResource"
import SettingsDialog from "@/components/Settings/SettingsDialog.vue"
import useStudioStore from "@/stores/studioStore"

const APP_NAME = "cypress-settings"
const PRE_LOGIN_FETCHES = ["frappe.client.get_list", "frappe.client.get"]
// a 1x1 transparent PNG
const FAVICON = Cypress.Buffer.from(
	"iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==",
	"base64",
)

describe("settings dialog", () => {
	let store: ReturnType<typeof useStudioStore>

	// the app's auto-loaded resources fetch on import, before the spec has logged in
	before(() => {
		Cypress.on("uncaught:exception", (error) => !PRE_LOGIN_FETCHES.some((url) => error.message.includes(url)))
	})

	after(() => {
		cy.login()
		cy.remove_doc("Studio App", APP_NAME, true)
	})

	beforeEach(() => {
		setActivePinia(pinia)
		store = useStudioStore()
		store.showSettingsDialog = false
		cy.login()
		cy.intercept("/api/method/frappe.client.set_value").as("save")
		cy.remove_doc("Studio App", APP_NAME, true)
		cy.insert_doc("Studio App", { app_name: APP_NAME, app_title: "Cypress Settings" })
		cy.wrap(null).then(() => store.setApp(APP_NAME))
		cy.mount(SettingsDialog, { global: { plugins: [pinia, resourcesPlugin] } })
	})

	it("saves the app's title and favicon", () => {
		cy.wrap(null).then(() => store.openSettings("app"))
		cy.get("[role=tabpanel]").contains("label", "Title").parent().find("input").clear().type("Renamed App")
		cy.get("input[type=file]").selectFile(
			{ contents: FAVICON, fileName: "cypress-favicon.png", mimeType: "image/png" },
			{ force: true },
		)
		cy.get("img[alt='App Favicon']").should("have.attr", "src").and("include", "cypress-favicon")
		cy.contains("button", "Save").click()
		cy.wait("@save")

		cy.get_doc("Studio App", APP_NAME).then(({ data }) => {
			expect(data.app_title).to.eq("Renamed App")
			expect(data.favicon).to.include("cypress-favicon")
		})
		cy.wrap(null).should(() => expect(store.activeApp?.favicon).to.include("cypress-favicon"))
	})

	it("removes the favicon", () => {
		cy.update_doc("Studio App", APP_NAME, { favicon: "/files/old-favicon.png" })
		cy.wrap(null).then(() => store.setApp(APP_NAME))
		cy.wrap(null).then(() => store.openSettings("app"))
		cy.contains("button", "Remove").click()
		cy.get("img[alt='App Favicon']").should("have.attr", "src", "/assets/studio/frontend/favicon.png")
		cy.contains("button", "Save").click()
		cy.wait("@save")
		cy.get_doc("Studio App", APP_NAME).its("data.favicon").should("not.be.ok")
	})

	it("opens on the requested tab", () => {
		cy.wrap(null).then(() => store.openSettings("editor"))
		cy.contains("label", "OpenRouter API Key").should("be.visible")
		cy.contains("[role=tab]", "App").click()
		cy.contains("label", "App Route").should("be.visible")
	})
})
