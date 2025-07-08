import "./index.css"

import { createApp } from "vue"
import { createPinia } from "pinia"
import "./setupFrappeUIResource"
import app_router from "@/router/app_router"
import AppRenderer from "./AppRenderer.vue"
import { resourcesPlugin } from "frappe-ui"
import { registerGlobalComponents } from "./globals"

// For rendering apps built by studio
const app = createApp(AppRenderer)
const pinia = createPinia()

app.use(app_router)
app.use(pinia)
app.use(resourcesPlugin)
registerGlobalComponents(app)
window.__APP_COMPONENTS__ = app._context.components

app.mount("#app")