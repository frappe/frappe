import "./index.css"

import { createApp } from "vue"
import { createPinia } from "pinia"
import studio_router from "@/router/studio_router"
import app_router from "@/router/app_router"
import App from "./App.vue"

import { setConfig, frappeRequest, resourcesPlugin, FeatherIcon } from "frappe-ui"
import { registerGlobalComponents } from "./globals"

const studio = createApp(App)
const pinia = createPinia()

setConfig("resourceFetcher", frappeRequest)

// For the main app builder
studio.use(studio_router)
studio.use(resourcesPlugin)
studio.use(pinia)
registerGlobalComponents(studio)
studio.mount("#studio")

// For rendering apps built by studio
const app = createApp(App)
app.use(app_router)
app.use(pinia)
app.component("FeatherIcon", FeatherIcon)
app.mount("#app")
