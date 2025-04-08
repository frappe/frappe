import { ref } from "vue"
import { createRouter, createWebHistory, NavigationGuardNext } from "vue-router"
import { createResource } from "frappe-ui"

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
]

let router = createRouter({
	history: createWebHistory("/studio"),
	routes,
})

let hasPermission: null | boolean = null
let sessionUser = ref("Guest")

router.beforeEach(async (to, _, next) => {
	if (isUserLoggedIn()) {
		sessionUser.value = getSessionUser()
		if (hasPermission === null) {
			try {
				const response = await createResource({
					url: "frappe.client.has_permission",
				}).submit({
					doctype: "Studio Page",
					docname: null,
					perm_type: "write",
				})
				hasPermission = response.has_permission
				return validatePermission(next)
			} catch (e) {
				hasPermission = false
				return validatePermission(next)
			}
		}
	}
	return validatePermission(next)
})

function validatePermission(next: NavigationGuardNext) {
	if (hasPermission) {
		next()
	} else {
		alert("You do not have permission to access this page")
		if (isUserLoggedIn()) {
			window.location.href = "/app"
		} else {
			window.location.href = "/login?redirect-to=/studio"
		}
	}
}

function isUserLoggedIn() {
	return document.cookie.includes("user_id") && !document.cookie.includes("user_id=Guest")
}

function getSessionUser() {
	return decodeURIComponent(document.cookie.split("user_id=")[1].split(";")[0]) || "Guest"
}

export default router
