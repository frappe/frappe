import { createApp } from "vue";
import RecorderRoot from "./RecorderRoot.vue";
import router from "./router.js";

let app = createApp(RecorderRoot).use(router);
SetVueGlobals(app);
app.mount(".recorder-container");
frappe.recorder.view = app;
