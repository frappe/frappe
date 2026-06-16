/* One-time cleanup flow for legacy Gravatar URLs stored before Gravatar support was removed.
 * Can be dropped when skip_gravatar_deletion_prompt is 1 for the majority of sites, or in the
 * next major release.
 */
frappe.provide("frappe.ui");

frappe.ui.maybe_show_legacy_gravatar_cleanup_prompt = function ({ onhide } = {}) {
	if (!frappe.boot.show_gravatar_deletion_prompt) {
		return false;
	}

	const dialog = new frappe.ui.Dialog({
		title: __("Delete Gravatar URLs"),
		fields: [
			{
				fieldname: "message",
				fieldtype: "HTML",
				options: `<p>${__(
					"Frappe no longer uses Gravatar because it can disclose hashed email addresses to a third-party service."
				)} <a href="https://github.com/frappe/frappe/issues/39869" target="_blank">${__(
					"Learn more"
				)}</a></p>
				<p>${
					frappe.utils.get_installed_apps().includes("erpnext")
						? __(
								"Existing Gravatar URLs may still be stored on User, Contact, and Lead records. Do you want to delete these URLs now?"
						  )
						: __(
								"Existing Gravatar URLs may still be stored on User and Contact records. Do you want to delete these URLs now?"
						  )
				}</p>`,
			},
			{
				fieldname: "delete_gravatar_urls",
				fieldtype: "Check",
				label: __("Delete Gravatar URLs"),
			},
			{
				fieldname: "skip_prompt",
				fieldtype: "Check",
				label: __("Don't show again"),
			},
		],
		primary_action_label: __("Confirm", null, "Confirm gravatar deletion prompt"),
		primary_action: ({ delete_gravatar_urls, skip_prompt }) => {
			return frappe
				.xcall("frappe.utils.legacy_gravatar_cleanup.submit_gravatar_deletion_prompt", {
					delete_gravatar_urls,
					skip_prompt,
				})
				.then((message) => {
					if (message?.queued) {
						frappe.show_alert({
							message: __("Gravatar URL deletion has been queued."),
							indicator: "blue",
						});
					}

					frappe.boot.show_gravatar_deletion_prompt = false;
				})
				.finally(() => dialog.hide());
		},
	});

	dialog.onhide = onhide;
	dialog.show();
	return true;
};
