import { createRouter, createWebHistory } from "vue-router"
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
	},
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
	// standard apps can only be edited in developer mode
	const appID = to.params.appID as string
	if (to.name === "StudioPage" && !window.is_developer_mode && (await isStandardApp(appID))) {
		return next({ name: "NotEditable", params: { appID }, replace: true })
	}
	return next()
})

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
