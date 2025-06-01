// Copyright (c) 2022, nts Technologies and contributors
// For license information, please see license.txt

nts.ui.form.on("Submission Queue", {
	refresh: function (frm) {
		if (frm.doc.status === "Queued" && nts.boot.user.roles.includes("System Manager")) {
			frm.add_custom_button(__("Unlock Reference Document"), () => {
				nts.confirm(
					`
					Are you sure you want to go ahead with this action?
					Doing this could unlock other submissions of this document which are in queue (if present)
					and could lead to non-ideal conditions.`,
					() => {
						frm.call("unlock_doc");
					}
				);
			});
		}
	},
});
