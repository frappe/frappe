import { createRouter, createWebHistory } from "vue-router"
import { session } from "@/data/session"
import { user } from "@/data/user"

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
]

let router = createRouter({
	history: createWebHistory("/desk"),
	routes,
})

router.beforeEach(async (to, _, next) => {
	const isLoggedIn = session.isLoggedIn

	try {
		await user.promise
	} catch (error) {
		isLoggedIn = false
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
