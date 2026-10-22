import { call } from "./api/frappe.js";

// Frappe renders the boot data into the page; the Vite dev server has no page template,
// so it asks the site instead (developer mode only).
export async function loadBoot() {
	if (window.flow_boot) {
		return {
			csrf_token: window.csrf_token,
			site_name: window.site_name,
			socketio_port: window.socketio_port,
			...window.flow_boot,
		};
	}
	const boot = await call("frappe.www.flow.index.get_context_for_dev");
	window.csrf_token = boot.csrf_token;
	return {
		csrf_token: boot.csrf_token,
		site_name: boot.site_name,
		socketio_port: boot.socketio_port,
		...boot.flow_boot,
	};
}
