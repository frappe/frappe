// Copyright (c) 2022, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.provide("frappe.process_bulk_transaction");

$.extend(frappe.process_bulk_transaction, {
    create: function (listview, from_doctype, to_doctype) {
        let checked_items = listview.get_checked_items();
        frappe.confirm(__("Create {0} {1} ?", [checked_items.length, to_doctype]), () => {
            frappe.call({
                method: "frappe.utils.bulk_transaction.process_bulk_transaction",
                args: {
                    data: checked_items,
                    from_doctype: from_doctype,
                    to_doctype: to_doctype
                },
                callback: function(r) {
                    if (!r.exc) {
                        if (!r.message) {
                            frappe.show_alert({
                                message: __(`Bulk creation of ${to_doctype}(s) has been enqueued.`),
                                indicator: 'green'
                            }, 5);
                        } else {
                            frappe.route_options = { name: ['in', r.message] }
                            frappe.set_route(['List', to_doctype, 'List']);
                        }
                    }
                }
            });
        });
    }
});