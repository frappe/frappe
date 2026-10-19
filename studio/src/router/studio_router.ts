import { createRouter, createWebHistory, type RouteLocationNormalized } from "vue-router"
import { call } from "frappe-ui"
import session from "@/utils/session"

const routes = [
	{
		path: "/home",
		name: "Home",
		component: () => import("@/pages/Home.vue"),
	},
	{
		path: "/",
		redirect: "home",
	},
	{
		path: "/app/:appID",
		name: "StudioApp",
		component: () => import("@/pages/StudioApp.vue"),
	},
	{
		path: "/app/:appID/:pageID",
		name: "StudioPage",
		component: () => import("@/pages/StudioPage.vue"),
		beforeEnter: blockStandardAppEditing,
	},
	{
		path: "/app/:appID/not-editable",
		name: "NotEditable",
		component: () => import("@/pages/NotEditable.vue"),
	},
	{
		path: "/not-permitted",
		name: "NotPermitted",
		component: () => import("@/pages/NotPermitted.vue"),
	},
	{
		path: "/:catchAll(.*)",
		name: "NotFound",
		component: () => import("@/pages/NotFound.vue"),
	}
]

let router = createRouter({
	history: createWebHistory("/studio"),
	routes,
})


router.beforeEach(async (to, _, next) => {
	!session.initialized && (await session.initialize())

	if (!session.isLoggedIn) {
		window.location.href = "/login?redirect-to=/studio"
		return next(false)
	}
	if (!session.hasPermission && to.path !== "/not-permitted") {
		return next("/not-permitted")
	}
	return next()
})

async function blockStandardAppEditing(to: RouteLocationNormalized) {
	if (window.is_developer_mode) return
	const appID = to.params.appID as string
	if (await isStandardApp(appID)) {
		return { name: "NotEditable", params: { appID }, replace: true }
	}
}

async function isStandardApp(appID: string) {
	try {
		const app = await call("frappe.client.get_value", {
			doctype: "Studio App",
			filters: appID,
			fieldname: "is_standard",
		})
		return Boolean(app?.is_standard)
	} catch {
		// the editor shows its own error for a missing or forbidden app
		return false
	}
}

// Patch router to resolve unmatched routes to NotFound page
// This ensures router-link renders correctly for the app being edited in studio
const resolve = router.resolve.bind(router)
// @ts-ignore
router.resolve = (to, currentLocation) => {
	let resolved
	try {
		resolved = resolve(to, currentLocation)
		if (!resolved.matched?.length) {
			resolved = resolve("/not-found", currentLocation)
		}
	} catch (error) {
		resolved = resolve("/not-found", currentLocation)
	}
	return resolved
}

export default router
