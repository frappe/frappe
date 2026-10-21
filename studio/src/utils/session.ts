import { computed, reactive } from "vue"
import { call } from "frappe-ui"

type SessionUser = {
	email: string
	full_name: string
	user_image: string
}

const emptyUser: SessionUser = {
	email: "",
	full_name: "",
	user_image: "",
}

//@ts-ignore
const session = reactive({
	initialized: false,
	user: { ...emptyUser },
	//@ts-ignore
	isLoggedIn: computed(() => session.user.email && session.user.email !== "Guest"),
	hasPermission: false,
	initialize,
	logout,
})

async function initialize() {
	if (session.initialized) return
	Object.assign(session.user, getSessionFromCookie())
	await fetchPermissions()
	session.initialized = true
}

function getSessionFromCookie() {
	return document.cookie
		.split("; ")
		.map((c) => c.split("="))
		.reduce((acc, [key, value]) => {
			key = key === "user_id" ? "email" : key
			acc[key] = decodeURIComponent(value)
			return acc
		}, {} as any)
}

async function fetchPermissions() {
	if (!session.isLoggedIn) return
	const has_permission = await call("studio.api.check_app_permission")
	session.hasPermission = Boolean(has_permission)
}

async function logout() {
	resetSession()
	await call("logout")
	window.location.reload()
}

function resetSession() {
	Object.assign(session.user, { ...emptyUser })
}

export default session
