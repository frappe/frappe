import "./index.css"

import { createApp } from "vue"
import router from "./router"
import "./setResourceFetcher"
import App from "./App.vue"

import {
	Button,
	FormControl,
	ErrorMessage,
	FeatherIcon,
	frappeRequest,
	resourcesPlugin,
} from "frappe-ui"

import Icon from "@/components/Icon.vue"

import { session } from "@/data/session"
import { user } from "@/data/user"

import dayjs from "@/utils/dayjs"

let app = createApp(App)

app.use(router)
app.use(resourcesPlugin)

app.component("Button", Button)
app.component("FormControl", FormControl)
app.component("ErrorMessage", ErrorMessage)
app.component("Icon", Icon)
app.component("FeatherIcon", FeatherIcon)

app.provide("$session", session)
app.provide("$user", user)
app.provide("$dayjs", dayjs)

declare global {
	interface Window {
		frappe: {
			boot?: object
		}
	}
}

if (import.meta.env.DEV) {
	frappeRequest({
		url: "/api/method/frappe.www.desk.get_context_for_dev",
	}).then((values: string) => {
		if (!window.frappe) window.frappe = {}
		window.frappe.boot = JSON.parse(values)
		app.mount("#app")
	})
} else {
	app.mount("#app")
}
