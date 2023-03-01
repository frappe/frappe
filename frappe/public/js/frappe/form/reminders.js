export class ReminderManager {
	constructor({ frm }) {
		this.frm = frm; // can be optional if not setting for document.
	}

	show() {
		let me = this;
		this.dialog = new frappe.ui.Dialog({
			title: __("Create a Reminder"),
			fields: [
				{
					fieldtype: "Select",
					label: __("Remind Me In"),
					fieldname: "remind_me_in",
					options: [
						{ label: __("30 minutes"), value: "30_minutes" },
						{ label: __("1 hour"), value: "1_hour" },
						{ label: __("4 hours"), value: "4_hours" },
						{ label: __("1 Day"), value: "1_day" },
						{ label: __("Custom"), value: "custom" },
					],
					default: "1_hour",
					onchange: () => {
						me._update_datetime_selector();
					},
				},
				{
					fieldtype: "Column Break",
					fieldname: "col_break_1",
				},
				{
					fieldtype: "Datetime",
					label: __("Remind At"),
					fieldname: "remind_at",
					reqd: 1,
					read_only: 1,
				},
				{
					fieldtype: "Section Break",
					fieldname: "divider_between_message_and_time",
				},
				{
					fieldtype: "Small Text",
					label: __("Description"),
					fieldname: "description",
					reqd: 1,
				},
			],
			primary_action_label: __("Create"),
			primary_action: () => {
				this.create_reminder();
				this.dialog.hide();
			},
			secondary_action_label: __("Cancel"),
			secondary_action: () => {
				this.dialog.hide();
			},
		});
		this._update_datetime_selector();
		this.dialog.show();
	}

	_update_datetime_selector() {
		this._convert_period_to_absolute_time();
		this.dialog.fields_dict.remind_at.df.read_only =
			this.dialog.get_value("remind_me_in") != "custom";
		this.dialog.fields_dict.remind_at.refresh();
		this.dialog.fields_dict.remind_at.datepicker?.update({
			minDate: frappe.datetime.str_to_obj(frappe.datetime.now_datetime()),
		});
	}

	_convert_period_to_absolute_time() {
		const period = this.dialog.get_value("remind_me_in");
		if (!period || period == "custom") return;

		const now_time = frappe.datetime.str_to_obj(frappe.datetime.now_datetime());
		let [magnitude, unit] = period.split("_");

		let time_to_set = moment(now_time)
			.add(magnitude, unit)
			.format(frappe.defaultDatetimeFormat);
		this.dialog.set_value("remind_at", time_to_set);
	}

	create_reminder() {
		frappe
			.xcall("frappe.automation.doctype.reminder.reminder.create_new_reminder", {
				remind_at: this.dialog.get_value("remind_at"),
				description: this.dialog.get_value("description"),
				reminder_doctype: this.frm?.doc.doctype,
				reminder_docname: this.frm?.doc.name,
			})
			.then((reminder) => {
				frappe.show_alert(
					__("Reminder set at {0}", [frappe.datetime.str_to_user(reminder.remind_at)])
				);
			});
	}
}
