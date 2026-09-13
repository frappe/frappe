import { createApp } from "vue";
import { frappeRequest, setConfig } from "frappe-ui";

import App from "./App.vue";
import { router } from "./router.js";
import "./index.css";

// frappe-ui's list and document resources fetch through this
setConfig("resourceFetcher", frappeRequest);

createApp(App).use(router).mount("#app");
