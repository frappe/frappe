import { pinia } from "../support/component"

import { setActivePinia } from "pinia"
// @ts-ignore
import { resourcesPlugin } from "frappe-ui"

import "@/setupFrappeUIResource"
import SettingsDialog from "@/components/Settings/SettingsDialog.vue"
import useStudioStore from "@/stores/studioStore"
import type { StudioPage } from "@/types/Studio/StudioPage"

const APP_NAME = "cypress-settings"
const PRE_LOGIN_FETCHES = ["frappe.client.get_list", "frappe.client.get"]
// a 1x1 transparent PNG
const FAVICON = Cypress.Buffer.from(
	"iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==",
	"base64",
)

describe("settings dialog", () => {
	let store: ReturnType<typeof useStudioStore>
	let aboutPage: StudioPage
	let contactPage: StudioPage

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
		cy.viewport(1400, 900)
		store = useStudioStore()
		store.showSettingsDialog = false
		cy.login()
		cy.intercept("/api/method/frappe.client.set_value").as("save")
		cy.remove_doc("Studio App", APP_NAME, true)
		cy.insert_doc("Studio App", { app_name: APP_NAME, app_title: "Cypress Settings" })
		cy.insert_doc("Studio Page", { studio_app: APP_NAME, page_title: "About" }).then((page) => (aboutPage = page))
		cy.insert_doc("Studio Page", { studio_app: APP_NAME, page_title: "Contact" }).then((page) => (contactPage = page))
		cy.wrap(null).then(() => store.setApp(APP_NAME))
		cy.mount(SettingsDialog, { global: { plugins: [pinia, resourcesPlugin] } })
	})

	it("saves the title when it changes", () => {
		cy.wrap(null).then(() => store.openSettings("app"))
		cy.contains("label", "Title").parent().find("input").clear().type("Renamed App").blur()
		cy.wait("@save")
		cy.get_doc("Studio App", APP_NAME).its("data.app_title").should("eq", "Renamed App")
	})

	it("saves the favicon on upload", () => {
		cy.wrap(null).then(() => store.openSettings("app"))
		cy.get("input[type=file]").selectFile(
			{ contents: FAVICON, fileName: "cypress-favicon.png", mimeType: "image/png" },
			{ force: true },
		)
		cy.wait("@save")
		cy.get_doc("Studio App", APP_NAME).its("data.favicon").should("include", "cypress-favicon")
		cy.get("img[alt='App Favicon']").should("have.attr", "src").and("include", "cypress-favicon")
	})

	it("removes the favicon", () => {
		cy.update_doc("Studio App", APP_NAME, { favicon: "/files/old-favicon.png" })
		cy.wrap(null).then(() => store.setApp(APP_NAME))
		cy.wrap(null).then(() => store.openSettings("app"))
		cy.contains("button", "Remove").click()
		cy.wait("@save")
		cy.get_doc("Studio App", APP_NAME).its("data.favicon").should("not.be.ok")
		cy.get("img[alt='App Favicon']").should("have.attr", "src").and("include", "favicon.png")
	})

	it("sets the app home", () => {
		cy.wrap(null).then(() => store.openSettings("app"))
		cy.contains("label", "App Home").parent().find("button").click()
		cy.contains("[role=option]", "Contact").click()
		cy.wait("@save")
		cy.get_doc("Studio App", APP_NAME).its("data.app_home").should("eq", contactPage.name)
	})

	it("allows guests on a page that isn't open", () => {
		cy.wrap(null).then(() => store.openSettings("pages"))
		guestSwitch("About").click()
		cy.wait("@save")
		cy.get_doc("Studio Page", aboutPage.name).its("data.allow_guest").should("eq", 1)
		guestSwitch("Contact").should("have.attr", "aria-checked", "false")
	})

	it("shows export settings only in developer mode", () => {
		cy.wrap(null).then(() => store.openSettings("app"))
		cy.contains("Enable App Export").should("not.exist")
		cy.contains("button", "Editor").click()
		cy.window().then((win) => (win.is_developer_mode = true))
		cy.contains("button", "App").click()
		cy.contains("Enable App Export").parents(".justify-between").first().find("[role=switch]").click()
		cy.contains("span", /^Frappe App$/).should("be.visible")
		cy.contains("button", "Update").scrollIntoView().should("be.visible").and("be.disabled")
		cy.window().then((win) => delete win.is_developer_mode)
	})

	it("opens on the requested tab", () => {
		cy.wrap(null).then(() => store.openSettings("editor"))
		cy.contains("label", "OpenRouter API Key").should("be.visible")
		cy.contains("button", "App").click()
		cy.contains("label", "Route").should("be.visible")
	})

	function guestSwitch(pageTitle: string) {
		return cy.get(`[role=switch][aria-label="Allow guest access to ${pageTitle}"]`)
	}
})
