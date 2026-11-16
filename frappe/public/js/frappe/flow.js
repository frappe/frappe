frappe.provide("frappe.flow");

/** Whether Flow can chat on this site. The same for every user; check access to Flow separately. */
frappe.flow.is_enabled = function () {
	return Boolean(frappe.boot.flow_enabled);
};

/** Whether to offer Flow to this user: it can chat, or they can connect an AI service to set it up. */
frappe.flow.can_offer = function () {
	return (
		frappe.model.can_read("Flow Session") &&
		(frappe.flow.is_enabled() ||
			(frappe.model.can_create("Flow Provider") && frappe.model.can_create("Flow Model")))
	);
};
