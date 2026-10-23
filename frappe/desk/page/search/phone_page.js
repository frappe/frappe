import { onMounted, watch } from "vue";

// These pages are for phones. A wider screen has its own place for the same thing, so the
// page sends the reader there, replacing the route so Back does not land here again.
export function redirect_off_phone(...route) {
	if (window.frappe.is_mobile()) return false;
	window.frappe.route_flags.replace_route = true;
	window.frappe.set_route(...route);
	return true;
}

// Desk keeps a page's island mounted after the reader leaves and hands it a new route on
// every visit, so the screen is checked on each visit, not only at the first mount. `show`
// runs on a visit from a phone, `redirected` after sending a wider screen away.
export function on_phone_visit(props, desktop_route, show, redirected) {
	const visit = () => (redirect_off_phone(...desktop_route) ? redirected?.() : show());
	onMounted(visit);
	watch(() => props.route, visit);
}
