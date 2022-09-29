import { createApp } from "vue";
import RecorderRoot from "./RecorderRoot.vue";
import router from "./router.js";

frappe.recorder.view = createApp(RecorderRoot).use(router).mount(".recorder-container");
