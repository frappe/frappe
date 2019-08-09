frappe.views.GoogleDriveUploader = Class.extend({
	init: function(opts) {
		$.extend(this, opts);
		this.make();
	},
	make: function() {
		let me = this;
		let uploader = new frappe.ui.Dialog({
			title: __("Upload File to Google Drive"),
			fields: [
				{
					fieldtype: "Link",
					fieldname: "google_drive",
					options: "Google Drive",
					label: __("Google Drive"),
					reqd: 1,
					get_query: function() {
						return {
							"filters": {
								"owner": frappe.session.user,
							}
						}
					}
				}
			],
			primary_action_label: __("Submit"),
			primary_action: (d) => {
				frappe.show_alert({
					indicator: "red",
					message: __("Uploading to Google Drive.")
				});
				uploader.hide();
				frappe.call({
					method: "frappe.integrations.doctype.google_drive.google_drive.upload_document",
					args: {
						doctype: me.doctype,
						docname: me.docname,
						g_drive: d.google_drive,
					},
					callback: function(r) {
						frappe.show_alert({
							indicator: "green",
							message: __("Document uploaded to Google Drive.")
						});
						uploader.hide();
					}
				})
			}
		});
		uploader.show();
	}
})