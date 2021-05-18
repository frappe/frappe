erpnext.stock.move_item = function (item, source, target, actual_qty, rate, callback) {
	var dialog = new frappe.ui.Dialog();

	dialog.set_primary_action(__('Submit'), function () {

		// ruleid: frappe-disable-button-during-request
		frappe.call({
			method: 'erpnext.stock.doctype.stock_entry.stock_entry_utils.make_stock_entry',
			args: values,
			callback: function (r) {
				callback(r);
			},
		});
	});
};



erpnext.stock.move_item = function (item, source, target, actual_qty, rate, callback) {
	var dialog = new frappe.ui.Dialog();

	dialog.set_primary_action(__('Submit'), function () {

		// ok: frappe-disable-button-during-request
		frappe.call({
			method: 'erpnext.stock.doctype.stock_entry.stock_entry_utils.make_stock_entry',
			args: values,
			btn: dialog.get_primary_btn(),
			callback: function (r) {
				callback(r);
			},
		});
	});
};


