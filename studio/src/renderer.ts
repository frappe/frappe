import { createApp } from "vue"
import { createPinia } from "pinia"
import "./setupFrappeUIResource"
import app_router from "@/router/app_router"
import App from "./App.vue"
import { resourcesPlugin } from "frappe-ui"
import { registerGlobalComponents } from "./globals"

// For rendering apps built by studio
const app = createApp(App)
const pinia = createPinia()

app.use(app_router)
app.use(pinia)
app.use(resourcesPlugin)
registerGlobalComponents(app)

app.mount("#app")