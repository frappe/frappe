import { createRouter, createWebHistory } from "vue-router"
import { session } from "@/data/session"
import { user } from "@/data/user"
import { permissionsResource } from "@/data/permissions"

const routes = [
	{
		path: "/",
		name: "Home",
		component: () => import("@/pages/Home.vue"),
	},
	{
		path: "/login",
		name: "Login",
		component: () => import("@/pages/Login.vue"),
	},
	{
		path: "/:module",
		name: "Module",
		component: () => import("@/pages/Module.vue"),
	},
	{
		path: "/workspace/:name",
		name: "Workspace",
		component: () => import("@/pages/Workspace.vue"),
	},
	{
		// /desk/item/id
		// /desk/:doctype/:id
		path: "/:module/form/:doctype/:id",
		name: "Form",
		component: () => import("@/pages/Form.vue"),
	},
	{
		// TODO: reaching a doctype should be easy: /desk/item -> /desk/item/view/list
		path: "/:module/list/:id",
		name: "List",
		component: () => import("@/pages/List.vue"),
	},
	{
		path: "/:module/report/:id",
		name: "Report",
		component: () => import("@/pages/Report.vue"),
	},
	{
		path: "/:module/page/:id",
		name: "Page",
		component: () => import("@/pages/Page.vue"),
	},
	{
		path: "/:module/dashboard/:id",
		name: "Dashboard",
		component: () => import("@/pages/Dashboard.vue"),
	},
]

let router = createRouter({
	history: createWebHistory("/desk"),
	routes,
})

router.beforeEach(async (to, _, next) => {
	let isLoggedIn = session.isLoggedIn

	try {
		await user.promise
	} catch (error) {
		isLoggedIn = false
	}

	if (isLoggedIn && !permissionsResource?.data?.can_read) {
		await permissionsResource.reload()
	}

	if (to.name === "Login" && isLoggedIn) {
		next({ name: "Home" })
	} else if (to.name !== "Login" && !isLoggedIn) {
		next({ name: "Login" })
	} else {
		next()
	}
})

export default router
