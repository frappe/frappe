// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// License: GNU General Public License v3. See license.txt

frappe.ui.form.on('Newsletter', {
	refresh(frm) {
		let doc = frm.doc;
		if (!doc.__islocal && !cint(doc.email_sent) && !doc.__unsaved
				&& in_list(frappe.boot.user.can_write, doc.doctype)) {
			frm.add_custom_button(__('Send Now'), function() {
				frappe.confirm(__("Do you really want to send this email newsletter?"), function() {
					frm.call('send_emails').then(() => {
						frm.refresh();
					});
				});
			}, "fa fa-play", "btn-success");
		}

		frm.events.setup_dashboard(frm);

		if (doc.__islocal && !doc.send_from) {
			let { fullname, email } = frappe.user_info(doc.owner);
			frm.set_value('send_from', `${fullname} <${email}>`);
		}
	},

	onload_post_render(frm) {
		frm.trigger('setup_schedule_send');
	},

	setup_schedule_send(frm) {
		let today = new Date();

		// setting datepicker options to set min date & min time
		today.setHours(today.getHours() + 1 );
		frm.get_field('schedule_send').$input.datepicker({
			maxMinutes: 0,
			minDate: today,
			timeFormat: 'hh:00:00',
			onSelect: function (fd, d, picker) {
				if (!d) return;
				var date = d.toDateString();
				if (date === today.toDateString()) {
					picker.update({
						minHours: (today.getHours() + 1)
					});
				} else {
					picker.update({
						minHours: 0
					});
				}
				frm.get_field('schedule_send').$input.trigger('change');
			}
		});


		const $tp = frm.get_field('schedule_send').datepicker.timepicker;
		$tp.$minutes.parent().css('display', 'none');
		$tp.$minutesText.css('display', 'none');
		$tp.$minutesText.prev().css('display', 'none');
		$tp.$seconds.parent().css('display', 'none');
	},

	setup_dashboard(frm) {
		if(!frm.doc.__islocal && cint(frm.doc.email_sent)
			&& frm.doc.__onload && frm.doc.__onload.status_count) {
			var stat = frm.doc.__onload.status_count;
			var total = frm.doc.scheduled_to_send;
			if(total) {
				$.each(stat, function(k, v) {
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
	}
});
