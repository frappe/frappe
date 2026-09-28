import { pinia } from "../support/component"

import { h } from "vue"
import { setActivePinia } from "pinia"
// @ts-ignore
import { resourcesPlugin } from "frappe-ui"

import StudioCanvas from "@/components/StudioCanvas.vue"
import Block from "@/utils/block"
import { COMPONENTS } from "@/data/components"
import { getBlockInstance } from "@/utils/serializer"
import getBlockTemplate from "@/utils/blockTemplate"
import { registerGlobalComponents } from "@/globals"
import router from "@/router/studio_router"
import session from "@/utils/session"

const canvasElement = () => document.querySelector(".canvas") as HTMLElement

describe("canvas navigation guard", () => {
	beforeEach(() => {
		// satisfy the router's login guard without a site
		session.initialized = true
		session.user.email = "test@example.com"
		session.hasPermission = true
		if (!router.hasRoute("TestPage")) {
			router.addRoute({ path: "/app/test/page", name: "TestPage", component: { render: () => h("div") } })
		}
		cy.wrap(router.push("/app/test/page"))

		Block.setComponents(COMPONENTS)
		setActivePinia(pinia)
		cy.mount(StudioCanvas as any, {
			props: { componentTree: getBlockInstance({ ...getBlockTemplate("body") }) },
			global: { plugins: [pinia, router, resourcesPlugin, { install: registerGlobalComponents }] },
		})
		cy.get(".canvas").should("exist")
	})

	it("cancels navigation triggered by a click inside the canvas", () => {
		cy.then(() => {
			canvasElement().dispatchEvent(new MouseEvent("mousedown", { bubbles: true }))
			canvasElement().dispatchEvent(new MouseEvent("mouseup", { bubbles: true }))
			return router.push({ name: "Home" })
		})
		cy.wrap(null).should(() => expect(router.currentRoute.value.name).to.eq("TestPage"))
	})

	it("allows navigation after a press in the canvas is released outside it", () => {
		cy.then(() => {
			canvasElement().dispatchEvent(new MouseEvent("mousedown", { bubbles: true, button: 2 }))
			document.body.dispatchEvent(new MouseEvent("mouseup", { bubbles: true, button: 2 }))
		})
		cy.wait(10)
		cy.then(() => router.push({ name: "Home" }))
		cy.wrap(null).should(() => expect(router.currentRoute.value.name).to.eq("Home"))
	})
})
