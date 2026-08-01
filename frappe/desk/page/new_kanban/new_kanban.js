/**
 * Legacy #new-kanban/{board} entry. Always redirect to the standard Kanban route;
 * System Settings → Use New Kanban decides which UI opens.
 */
frappe.pages["new-kanban"].on_page_load = function () {
	redirect_new_kanban_to_list_route();
};

frappe.pages["new-kanban"].on_page_show = function () {
	redirect_new_kanban_to_list_route();
};

/** Resolve board → reference_doctype, then set_route List/{dt}/Kanban/{board}. */
function redirect_new_kanban_to_list_route() {
	const board_name = frappe.get_route()[1];
	if (!board_name) {
		frappe.set_route("List", "Kanban Board");
		return;
	}
	frappe.db.get_value("Kanban Board", board_name, "reference_doctype").then((r) => {
		const doctype = r?.message?.reference_doctype;
		if (!doctype) {
			frappe.msgprint(__("Kanban Board {0} not found.", [board_name]));
			return;
		}
		frappe.set_route("List", doctype, "Kanban", board_name);
	});
}
