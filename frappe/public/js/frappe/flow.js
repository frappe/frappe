frappe.provide("frappe.flow");

/** Whether Flow can chat on this site. The same for every user; check access to Flow separately. */
frappe.flow.is_enabled = function () {
	return Boolean(frappe.boot.flow_enabled);
};
