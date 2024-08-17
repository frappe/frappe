import "./index.css"

import { createApp } from "vue"
import { createPinia } from "pinia"
import router from "./router"
import App from "./App.vue"

import { setConfig, frappeRequest, resourcesPlugin } from "frappe-ui"
import { registerGlobalComponents } from "./globals"

const app = createApp(App)
const pinia = createPinia()

setConfig("resourceFetcher", frappeRequest)

app.use(router)
app.use(resourcesPlugin)
app.use(pinia)

registerGlobalComponents(app)

app.mount("#app")
