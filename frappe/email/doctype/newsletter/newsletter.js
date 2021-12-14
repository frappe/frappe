// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// License: GNU General Public License v3. See license.txt

frappe.ui.form.on('Newsletter', {
	refresh(frm) {
		let doc = frm.doc;
		let can_write = in_list(frappe.boot.user.can_write, doc.doctype);
		if (!frm.is_new() && !frm.is_dirty() && !doc.email_sent && can_write) {
			frm.add_custom_button(__('Send a test email'), () => {
				frm.events.send_test_email(frm);
			}, __('Preview'));

			frm.add_custom_button(__('Check broken links'), () => {
				frm.dashboard.set_headline(__('Checking broken links...'));
				frm.call('find_broken_links').then(r => {
					frm.dashboard.set_headline('');
					let links = r.message;
					if (links && links.length) {
						let html = '<ul>' + links.map(link => `<li>${link}</li>`).join('') + '</ul>';
						frm.dashboard.set_headline(__("Following links are broken in the email content: {0}", [html]));
					} else {
						frm.dashboard.set_headline(__("No broken links found in the email content"));
						setTimeout(() => {
							frm.dashboard.set_headline('');
						}, 3000);
					}
				});
			}, __('Preview'));

			frm.add_custom_button(__('Send now'), () => {
				if (frm.doc.schedule_send) {
					frappe.confirm(__("This newsletter was scheduled to send on a later date. Are you sure you want to send it now?"), function () {
						frm.call('send_emails').then(() => frm.refresh());
					});
					return;
				}
				frappe.confirm(__("Are you sure you want to send this newsletter now?"), function () {
					frm.call('send_emails').then(() => frm.refresh());
				});
			}, __('Send'));

			frm.add_custom_button(__('Schedule sending'), () => {
				frm.events.schedule_send_dialog(frm);
			}, __('Send'));
		}

		frm.events.setup_dashboard(frm);
		frm.events.setup_sending_status(frm);

		if (frm.is_new() && !doc.sender_email) {
			let { fullname, email } = frappe.user_info(doc.owner);
			frm.set_value('sender_email', email);
			frm.set_value('sender_name', fullname);
		}

		frm.trigger('update_schedule_message');
	},

	schedule_send_dialog(frm) {
		let hours = frappe.utils.range(24);
		let time_slots = hours.map(hour => {
			return `${(hour + '').padStart(2, '0')}:00`;
		});
		let d = new frappe.ui.Dialog({
			title: __('Schedule Newsletter'),
			fields: [
				{
					label: __('Date'),
					fieldname: 'date',
					fieldtype: 'Date',
					options: {
						minDate: new Date()
					}
				},
				{
					label: __('Time'),
					fieldname: 'time',
					fieldtype: 'Select',
					options: time_slots,
				},
			],
			primary_action_label: __('Schedule'),
			primary_action({ date, time }) {
				frm.set_value('schedule_sending', 1);
				frm.set_value('schedule_send', `${date} ${time}:00`);
				d.hide();
				frm.save();
			},
			secondary_action_label: __('Cancel Scheduling'),
			secondary_action() {
				frm.set_value('schedule_sending', 0);
				frm.set_value('schedule_send', '');
				d.hide();
				frm.save();
			}
		});
		if (frm.doc.schedule_sending) {
			let parts = frm.doc.schedule_send.split(' ');
			if (parts.length === 2) {
				let [date, time] = parts;
				d.set_value('date', date);
				d.set_value('time', time.slice(0, 5));
			}
		}
		d.show();
	},

	send_test_email(frm) {
		let d = new frappe.ui.Dialog({
			title: __('Send Test Email'),
			fields: [
				{
					label: __('Email'),
					fieldname: 'email',
					fieldtype: 'Data',
					options: 'Email',
				}
			],
			primary_action_label: __('Send'),
			primary_action({ email }) {
				d.get_primary_btn().text(__('Sending...')).prop('disabled', true);
				frm.call('send_test_email', { email })
					.then(() => {
						d.get_primary_btn().text(__('Send again')).prop('disabled', false);
					});
			}
		});
		d.show();
	},

	setup_dashboard(frm) {
		if (!frm.doc.__islocal && cint(frm.doc.email_sent)
			&& frm.doc.__onload && frm.doc.__onload.status_count) {
			var stat = frm.doc.__onload.status_count;
			var total = frm.doc.scheduled_to_send;
			if (total) {
				$.each(stat, function (k, v) {
					stat[k] = flt(v * 100 / total, 2) + '%';
				});

				frm.dashboard.add_progress("Status", [
					{
						title: stat["Not Sent"] + " Queued",
						width: stat["Not Sent"],
						progress_class: "progress-bar-info"
					},
					{
						title: stat["Sent"] + " Sent",
						width: stat["Sent"],
						progress_class: "progress-bar-success"
					},
					{
						title: stat["Sending"] + " Sending",
						width: stat["Sending"],
						progress_class: "progress-bar-warning"
					},
					{
						title: stat["Error"] + "% Error",
						width: stat["Error"],
						progress_class: "progress-bar-danger"
					}
				]);
			}
		}
	},

	setup_sending_status(frm) {
		frm.call('get_sending_status').then(r => {
			if (r.message) {
				frm.events.update_sending_progress(frm, r.message.sent, r.message.total);
			}
			if (r.message.sent >= r.message.total) {
				return;
			}
			if (frm.sending_status) return;

			frm.sending_status = setInterval(() => {
				if (frm.doc.email_sent && frm.$wrapper.is(':visible')) {
					frm.call('get_sending_status').then(r => {
						if (r.message) {
							let { sent, total } = r.message;
							frm.events.update_sending_progress(frm, sent, total);

							if (sent >= total) {
								clearInterval(frm.sending_status);
								frm.sending_status = null;
								return;
							}
						}
					});
				}
			}, 5000);
		});
	},

	update_sending_progress(frm, sent, total) {
		if (sent >= total) {
			frm.dashboard.hide_progress();
			return;
		}
		frm.dashboard.show_progress(__('Sending emails'), sent * 100 / total, __("{0} of {1} sent", [sent, total]));
	},

	on_hide(frm) {
		if (frm.sending_status) {
			clearInterval(frm.sending_status);
			frm.sending_status = null;
		}
	},

	update_schedule_message(frm) {
		if (!frm.doc.email_sent && frm.doc.schedule_send) {
			let datetime = frappe.datetime.global_date_format(frm.doc.schedule_send);
			frm.dashboard.set_headline_alert(__('This newsletter is scheduled to be sent on {0}', [datetime.bold()]));
		} else {
			frm.dashboard.clear_headline();
		}
	}
});
