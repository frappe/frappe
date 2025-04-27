// Copyright (c) 2019, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on("Comment", {
	refresh: function (frm) {
		if (frm.is_new() || frm.doc.comment_type != "Comment") {
			return;
		}
		const type =
			["Spam", "Discard"].includes(frm.doc.spam_type) && frm.doc.spam_type != "Pending"
				? "Ham"
				: "Spam";
		if (frm.doc.spam_type != "Pending") {
			frm.add_custom_button(__(`Mark as ${type}`), () => mark_as_spam_or_ham(frm, type));
		} else {
			frm.add_custom_button(
				__(`Mark as Ham`),
				() => mark_as_spam_or_ham(frm, "hame"),
				__("Actions")
			);
			frm.add_custom_button(
				__(`Mark as Spam`),
				() => mark_as_spam_or_ham(frm, "Spam"),
				__("Actions")
			);
		}
	},
});

function mark_as_spam_or_ham(frm, spam_type) {
	frappe.call({
		method: "frappe.core.doctype.comment.comment.mark_as_spam_or_ham",
		args: {
			comment: frm.doc.name,
			type: spam_type,
		},
		freeze: true,
		callback: function (r) {
			if (r) {
				frm.reload_doc();
			}
		},
	});
}
