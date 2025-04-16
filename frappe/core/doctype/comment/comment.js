// Copyright (c) 2019, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on("Comment", {
	refresh: function (frm) {
		if (frm.is_new() || frm.doc.comment_type != "Comment") {
			return;
		}
		const is_spam =
			["Spam", "Discard"].includes(frm.doc.spam_type) && frm.doc.spam_type != "Pending";
		frm.add_custom_button(__(`Mark as ${is_spam ? "Ham" : "Spam"}`), function () {
			frm.call("mark_as_spam_or_ham", { is_spam: !is_spam })
				.then((r) => {
					if (r.message) {
						frm.reload_doc();
					}
				})
				.catch((e) => {
					frappe.msgprint(__("Unable to mark comment as spam/ham"));
					console.error(e);
				});
		});
	},
});
