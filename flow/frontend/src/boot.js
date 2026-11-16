import { call } from "./api/frappe.js";

// /flow renders the boot data into the page; the launcher's panel asks for it on first open,
// and takes the session's token and the socket's address from the page around it: Desk's boot,
// or the globals a frappe-ui app renders.
export async function loadBoot(rendered) {
	if (rendered) return rendered;
	const desk = window.frappe?.boot;
	window.csrf_token ||= window.frappe?.csrf_token;
	return {
		csrf_token: window.csrf_token,
		site_name: desk?.sitename ?? window.site_name,
		socketio_port: desk?.socketio_port ?? window.socketio_port,
		...(await call("frappe.flow.api.boot")),
	};
}
