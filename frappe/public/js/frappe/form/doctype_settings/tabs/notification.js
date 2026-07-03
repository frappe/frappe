const CHANNEL_COLORS = {
	Email: "blue",
	SMS: "green",
	Slack: "purple",
	"System Notification": "orange",
};

const CHANNEL_ICONS = {
	Email: "mail",
	SMS: "smartphone",
	Slack: "slack",
	"System Notification": "bell",
};

frappe.doctype_settings.register("notifications", function (panel, doctype) {
	const open = (name) => {
		panel.dialog.hide();
		frappe.set_route("Form", "Notification", name);
	};
	const create = () => {
		panel.dialog.hide();
		frappe.new_doc("Notification", { document_type: doctype });
	};

	frappe.doctype_settings.render_list(panel, {
		title: __("Notifications"),
		description: __("Send automatic notifications for events on any {0}.", [doctype]),
		show_header: true,
		primary_action: { label: __("New"), icon: "plus", onclick: create },
		load: () =>
			frappe.db.get_list("Notification", {
				filters: { document_type: doctype },
				fields: ["name", "event", "channel", "enabled"],
				order_by: "name asc",
				limit: 0,
			}),
		title_column: {
			label: __("Name"),
			primary: (r) => r.name,
			onclick: (r) => open(r.name),
			// Flag only the off state; enabled rows stay clean.
			tags: (r) => (r.enabled ? [] : [{ label: __("Disabled"), color: "gray" }]),
		},
		columns: [
			{
				label: __("Event"),
				badge: (r) => (r.event ? { label: __(r.event), color: "gray" } : null),
			},
			{
				label: __("Channel"),
				badge: (r) =>
					r.channel
						? {
								label: __(r.channel),
								color: CHANNEL_COLORS[r.channel] || "gray",
								icon: CHANNEL_ICONS[r.channel],
						  }
						: null,
			},
		],
		actions: (r) => [
			{
				label: r.enabled ? __("Disable") : __("Enable"),
				icon: r.enabled ? "ban" : "circle-check",
				onclick: (list) =>
					frappe.db
						.set_value("Notification", r.name, { enabled: r.enabled ? 0 : 1 })
						.then(() => {
							frappe.show_alert({
								message: r.enabled ? __("Disabled") : __("Enabled"),
								indicator: "green",
							});
							list.reload();
						}),
			},
			{ label: __("Preview"), icon: "eye", onclick: () => preview(r.name) },
			{ label: __("Duplicate"), icon: "copy", onclick: () => duplicate(panel, r.name) },
			{ label: __("Edit"), icon: "pencil", onclick: () => open(r.name) },
			{
				label: __("Delete"),
				icon: "trash-2",
				danger: true,
				// frappe.model.delete_doc handles the confirm prompt, delete sound and
				// locals cleanup; the callback runs only on success.
				onclick: (list) =>
					frappe.model.delete_doc("Notification", r.name, () => {
						frappe.show_alert({ message: __("Deleted"), indicator: "green" });
						list.reload();
					}),
			},
		],
		empty_state: {
			icon: frappe.doctype_settings.tab_icon("notifications"),
			title: __("No notifications configured"),
			description: __("Create a notification to alert users about {0} events.", [doctype]),
			action: { label: __("New Notification"), onclick: create },
		},
	});
});

// Clone via the same client API as the form's "Duplicate": copy_doc handles child
// tables, then open the new (disabled) notification as an unsaved form to review + save.
function duplicate(panel, notification) {
	frappe.model.with_doctype("Notification", () => {
		frappe.model.with_doc("Notification", notification, () => {
			const newdoc = frappe.model.copy_doc(frappe.get_doc("Notification", notification));
			newdoc.enabled = 0;
			panel.dialog.hide();
			frappe.set_route("Form", "Notification", newdoc.name);
		});
	});
}

// Reuse the same previewer the Notification form's "Preview" button uses: it picks a
// sample document and calls the notification's whitelisted preview_* methods itself.
function preview(notification) {
	frappe.db.get_doc("Notification", notification).then((doc) => {
		new frappe.views.RenderPreviewer({
			doc,
			doctype: doc.document_type,
			preview_fields: [
				{
					label: __("Meets Condition?"),
					fieldtype: "Data",
					method: "preview_meets_condition",
				},
				{ label: __("Subject"), fieldtype: "Data", method: "preview_subject" },
				{ label: __("Message"), fieldtype: "Code", method: "preview_message" },
			],
		});
	});
}
