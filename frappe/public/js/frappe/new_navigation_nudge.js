/* The one-time invitation to try the module-first navigation, shown only to a site that
 * arrived on the icon grid. See frappe/utils/new_navigation_nudge.py for what turns it on
 * and when this whole flow can be dropped.
 */
frappe.provide("frappe.ui");

frappe.ui.maybe_show_new_navigation_prompt = function ({ onhide } = {}) {
	if (!frappe.boot.show_new_navigation_prompt) {
		return false;
	}

	const submit = (action) =>
		frappe
			.xcall("frappe.utils.new_navigation_nudge.submit_new_navigation_prompt", { action })
			.then((message) => {
				frappe.boot.show_new_navigation_prompt = false;

				if (message === "switched") {
					frappe.show_alert({
						message: __("Switched to the new navigation. Reloading…"),
						indicator: "green",
					});
					setTimeout(() => window.location.reload(), 1000);
				} else {
					frappe.show_alert({
						message: __("Keeping the icon grid."),
						indicator: "blue",
					});
				}
			})
			.finally(() => dialog.hide());

	const dialog = new frappe.ui.Dialog({
		title: __("Try the new navigation"),
		fields: [
			{
				fieldname: "message",
				fieldtype: "HTML",
				options: `<p>${__(
					"Your desktop now has a second form: modules in a dock, each with a sidebar of its own, instead of a grid of icons."
				)}</p>
				<p>${__(
					"Nothing is deleted either way — your icons and their arrangement stay exactly as they are, and you can switch back from Desktop Settings at any time."
				)}</p>`,
			},
		],
		primary_action_label: __("Try it"),
		primary_action: () => submit("try_new_navigation"),
		secondary_action_label: __("Keep the icon grid"),
		secondary_action: () => submit("keep_icon_grid"),
	});

	dialog.onhide = onhide;
	dialog.show();
	return true;
};
