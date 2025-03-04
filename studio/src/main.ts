import "./index.css"

import { createApp } from "vue"
import { createPinia } from "pinia"
import studio_router from "@/router/studio_router"
import "./setupFrappeUIResource"
import App from "./App.vue"

import { resourcesPlugin } from "frappe-ui"
import { registerGlobalComponents } from "./globals"

const studio = createApp(App)
const pinia = createPinia()

// For the main app builder
studio.use(studio_router)
studio.use(resourcesPlugin)
studio.use(pinia)
registerGlobalComponents(studio)
studio.mount("#studio")
