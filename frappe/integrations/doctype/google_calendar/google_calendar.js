// Copyright (c) 2019, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on("Google Calendar", {
	refresh: function(frm) {
		if (frm.is_new()) {
			frm.dashboard.set_headline(__("To use Google Calendar, enable {0}.", [`<a href='/app/google-settings'>${__('Google Settings')}</a>`]));
		}
		else if (frm.doc.refresh_token === undefined) {
			frm.dashboard.set_headline(__("To sync Calendar events please 'Authorize Google Calendar Access'"));
		}

		frappe.realtime.on("import_google_calendar", (data) => {
			if (data.progress) {
				frm.dashboard.show_progress("Syncing Google Calendar", data.progress / data.total * 100,
					__("Syncing {0} of {1}", [data.progress, data.total]));
				if (data.progress === data.total) {
					frm.dashboard.hide_progress("Syncing Google Calendar");
				}
			}
		});

		if (frm.doc.refresh_token) {
			frm.add_custom_button(__("Sync Calendar"), function () {
				frappe.show_alert({
					indicator: "green",
					message: __("Syncing. Calendar events will be imported in some time.")
				});
				$('[data-label="Sync%20Calendar"]').html("Syncing Events");
				$('[data-label="Sync%20Calendar"]').prop("disabled", true);
				frappe.call({
					method: "frappe.integrations.doctype.google_calendar.google_calendar.sync",
					args: {
						"g_calendar": frm.doc.name
					},
				}).then((r) => {
					$('[data-label="Sync%20Calendar"]').prop("disabled", false);
					frappe.hide_progress();
					frm.reload_doc();
				});
			});
		}
		if (frm.doc.last_sync_datetime !== undefined) {
			frm.trigger("show_sync_alert");
			frm.add_custom_button(__("View Google Calendar"), function () {
				window.open(
					frappe.urllib.get_full_url("/app/event/view/calendar/default")
				);
			});
		}
	},
	authorize_google_calendar_access: function(frm) {
		let reauthorize = 0;
		if(frm.doc.authorization_code) {
			reauthorize = 1;
		}

		frappe.call({
			method: "frappe.integrations.doctype.google_calendar.google_calendar.authorize_access",
			args: {
				"g_calendar": frm.doc.name,
				"reauthorize": reauthorize
			},
			callback: function(r) {
				if(!r.exc) {
					frm.save();
					window.open(r.message.url);
				}
			}
		});
	},
	show_sync_alert: function(frm) {
		frm.dashboard.clear_headline();
		frm.dashboard.set_headline(__("Last Synced at {0}.", [new Date(frm.doc.last_sync_datetime).toLocaleString()]));
	}
});