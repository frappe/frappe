import "./index.css"

import { createApp } from "vue"
import router from "./router"
import App from "./App.vue"

import {
	Button,
	FormControl,
	ErrorMessage,
	setConfig,
	frappeRequest,
	resourcesPlugin,
} from "frappe-ui"

import { session } from "@/data/session"
import { user } from "@/data/user"

let app = createApp(App)

setConfig("resourceFetcher", frappeRequest)

app.use(router)
app.use(resourcesPlugin)

app.component("Button", Button)
app.component("FormControl", FormControl)
app.component("ErrorMessage", ErrorMessage)

app.provide("$session", session)
app.provide("$user", user)

if (import.meta.env.DEV) {
	frappeRequest({
		url: "/api/method/frappe.www.desk.get_context_for_dev",
	}).then((values) => {
		if (!window.frappe) window.frappe = {}
		window.frappe.boot = JSON.parse(values)
		app.mount("#app")
	})
} else {
	app.mount("#app")
}
