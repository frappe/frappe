import { pinia } from "../support/component"

import { setActivePinia } from "pinia"
import { createMemoryHistory, createRouter } from "vue-router"
// @ts-ignore
import { resourcesPlugin } from "frappe-ui"

import "@/setupFrappeUIResource"
import SettingsDialog from "@/components/Settings/SettingsDialog.vue"
import useStudioStore from "@/stores/studioStore"
import type { StudioPage } from "@/types/Studio/StudioPage"

const APP_NAME = "cypress-settings"
const RENAMED_APP = "cypress-settings-renamed"
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
	let router: ReturnType<typeof editorRouter>

	// the app's auto-loaded resources fetch on import, before the spec has logged in
	before(() => {
		Cypress.on("uncaught:exception", (error) => !PRE_LOGIN_FETCHES.some((url) => error.message.includes(url)))
	})

	after(() => {
		cy.login()
		cy.remove_doc("Studio App", APP_NAME, true)
		cy.remove_doc("Studio App", RENAMED_APP, true)
	})

	beforeEach(() => {
		setActivePinia(pinia)
		cy.viewport(1400, 900)
		store = useStudioStore()
		store.showSettingsDialog = false
		cy.login()
		cy.intercept("/api/method/frappe.client.set_value").as("save")
		cy.remove_doc("Studio App", APP_NAME, true)
		cy.remove_doc("Studio App", RENAMED_APP, true)
		cy.insert_doc("Studio App", { app_name: APP_NAME, app_title: "Cypress Settings" })
		cy.insert_doc("Studio Page", { studio_app: APP_NAME, page_title: "About" }).then((page) => (aboutPage = page))
		cy.insert_doc("Studio Page", { studio_app: APP_NAME, page_title: "Contact" }).then((page) => (contactPage = page))
		cy.wrap(null).then(() => store.setApp(APP_NAME))
		cy.wrap(null).then(() => {
			router = editorRouter()
			return router.push({ name: "StudioPage", params: { appID: APP_NAME, pageID: aboutPage.name } })
		})
		cy.then(() => cy.mount(SettingsDialog, { global: { plugins: [pinia, resourcesPlugin, router] } }))
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

	it("edits a page's title, route and guest access from its row", () => {
		cy.wrap(null).then(() => store.openSettings("pages"))
		cy.get('button[aria-label="Edit About"]').click()
		cy.contains("label", "Title").parent().find("input").clear().type("About Us")
		cy.contains("label", "Route").parent().find("input").clear().type("about-us")
		cy.contains("[role=dialog]", "Edit Page").find("[role=switch]").click()
		cy.contains("button", "Save").click()
		cy.wait(["@save", "@save", "@save"])
		cy.get_doc("Studio Page", aboutPage.name).then(({ data }) => {
			expect(data.page_title).to.eq("About Us")
			expect(data.route).to.eq("/about-us")
			expect(data.allow_guest).to.eq(1)
		})
		guestSwitch("About Us").should("have.attr", "aria-checked", "true")
		cy.contains("h2", "Pages").should("be.visible")
		cy.get("[role=cell]").should("contain.text", "About Us").and("contain.text", "/about-us")
	})

	it("toggles guest access without opening the page editor", () => {
		cy.wrap(null).then(() => store.openSettings("pages"))
		guestSwitch("Contact").click()
		cy.wait("@save")
		cy.contains("Edit Page").should("not.exist")
	})

	it("shows export settings only in developer mode", () => {
		cy.wrap(null).then(() => store.openSettings("app"))
		cy.contains("Enable App Export").should("not.exist")
		cy.contains("button", "AI").click()
		cy.window().then((win) => (win.is_developer_mode = true))
		cy.contains("button", "App").click()
		cy.contains("Enable App Export").parents(".justify-between").first().find("[role=switch]").click()
		cy.contains("span", /^Frappe App$/).should("be.visible")
		cy.contains("button", "Update").scrollIntoView().should("be.visible").and("be.disabled")
		cy.window().then((win) => delete win.is_developer_mode)
	})

	it("renames the app and moves the editor to its new URL", () => {
		cy.intercept("/api/method/run_doc_method").as("rename")
		cy.wrap(null).then(() => store.openSettings("app"))
		cy.get('button[aria-label="Rename App"]').click()
		cy.contains("label", "App Name").parent().find("input").clear().type(RENAMED_APP)
		cy.contains("button", "Rename").click()
		cy.wait("@rename")
		// the dialog closes once the renamed app has fully loaded
		cy.contains("label", "App Name").should("not.exist")
		cy.get_doc("Studio App", RENAMED_APP).its("data.app_name").should("eq", RENAMED_APP)
		cy.wrap(null).should(() => {
			expect(router.currentRoute.value.params.appID).to.eq(RENAMED_APP)
			expect(router.currentRoute.value.params.pageID).to.eq(aboutPage.name)
			expect(store.activeApp?.name).to.eq(RENAMED_APP)
		})
	})

	it("shows why a rename was refused", () => {
		cy.wrap(null).then(() => store.openSettings("app"))
		cy.get('button[aria-label="Rename App"]').click()
		cy.contains("label", "App Name").parent().find("input").clear().type("Not Valid")
		cy.contains("button", "Rename").click()
		cy.contains("App Name can only have lowercase letters").should("be.visible")
		cy.wrap(null).should(() => expect(router.currentRoute.value.params.appID).to.eq(APP_NAME))
	})

	it("opens on the requested tab", () => {
		cy.wrap(null).then(() => store.openSettings("ai"))
		cy.contains("label", "OpenRouter API Key").should("be.visible")
		cy.contains("button", "App").click()
		cy.contains("label", "Route").should("be.visible")
	})

	function guestSwitch(pageTitle: string) {
		return cy.get(`[role=switch][aria-label="Allow guest access to ${pageTitle}"]`)
	}
})

function editorRouter() {
	return createRouter({
		history: createMemoryHistory(),
		routes: [{ path: "/app/:appID/:pageID", name: "StudioPage", component: { render: () => null } }],
	})
}
