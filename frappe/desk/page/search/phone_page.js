// These pages are for phones. A wider screen has its own place for the same thing, so the
// page sends the reader there, replacing the route so Back does not land here again.
export function redirect_off_phone(...route) {
	if (window.frappe.is_mobile()) return false;
	window.frappe.route_flags.replace_route = true;
	window.frappe.set_route(...route);
	return true;
}
