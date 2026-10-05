/* The one-time invitation to try the module-first navigation, shown only to a site that
 * arrived on the icon grid. See frappe/utils/new_navigation_nudge.py for what turns it on
 * and when this whole flow can be dropped.
 */
frappe.provide("frappe.ui");

frappe.ui.maybe_show_new_navigation_prompt = function ({ onhide } = {}) {
	if (
		!frappe.boot.show_new_navigation_prompt ||
		(frappe.get_route()[0] || frappe.boot.home_page) !== "desktop"
	) {
		return false;
	}

	const submit = (action) =>
		frappe
			.xcall("frappe.utils.new_navigation_nudge.submit_new_navigation_prompt", { action })
			.then((message) => {
				frappe.boot.show_new_navigation_prompt = false;

				if (message === "switched") {
					frappe.show_alert({
						message: __("Switching you to the new navigation…"),
						indicator: "green",
					});
					setTimeout(() => window.location.reload(), 1000);
				} else {
					frappe.show_alert({
						message: __("No problem. You can try it anytime from Desktop Settings."),
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
				options: `<p>${__("Navigation on the desktop has two modes:")}</p>
				<ul>
					<li>${__("{0}: a grid of icons you can arrange, which is what you use today.", [
						`<b>${__("Desktop Icons")}</b>`,
					])}</li>
					<li>${__("{0}: your modules sit in a dock, and each one has its own sidebar.", [
						`<b>${__("Apps")}</b>`,
					])}</li>
				</ul>
				<p>${__(
					"Your icons and their layout stay just as they are, and you can switch back anytime from Desktop Settings."
				)}</p>
				<p><a href="https://docs.frappe.io/framework/user/en/desk/navigation/migrating-to-the-new-navigation" target="_blank" rel="noopener noreferrer">${__(
					"Read the migration guide"
				)}</a></p>`,
			},
		],
		primary_action_label: __("Try it"),
		primary_action: () => submit("try_new_navigation"),
		secondary_action_label: __("No thanks"),
		secondary_action: () => submit("keep_icon_grid"),
	});

	dialog.onhide = onhide;
	dialog.show();
	return true;
};
