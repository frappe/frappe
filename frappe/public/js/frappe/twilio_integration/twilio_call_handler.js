frappe.provide('frappe.phone_call');
import { Device } from 'twilio-client';

class TwilioCall {
	constructor(to_number, frm) {
		// to_number call be string or array
		// like '12345' or ['1234', '4567'] or '1234\n4567'

		frappe.call({
			method: "frappe.integrations.doctype.twilio_settings.twilio_settings.get_access_token",
			callback: (access_token) => { this.setup_device(access_token); }
		})

		if (Array.isArray(to_number)) {
			this.to_numbers = to_number;
		} else {
			this.to_numbers = to_number.split('\n');
		}
		if (frm) {
			this.document_to_link = {
				'link_doctype': frm.doctype,
				'link_name': frm.docname
			};
		}
		this.make();
	}
	make() {
		this.dialog = new frappe.ui.Dialog({
			'static': 1,
			'title': __('Make a Call'),
			'minimizable': true,
			'fields': [{
				'fieldname': 'to_number',
				'label': 'To Number',
				'fieldtype': 'Autocomplete',
				'ignore_validation': true,
				'options': this.to_numbers,
				'read_only': 0,
				'reqd': 1
			}, {
				'fieldname': 'select_audio',
				'label': 'Active Audio Output',
				'fieldtype': 'Select',
				'ignore_validation': true,
				'options': this.get_audio_devices(),
				'read_only': 0,
				'reqd': 1
			}, {
				'label': 'Response',
				'fieldtype': 'Section Break',
				'collapsible': 1
			}, {
				'fieldname': 'response',
				'label': 'Response',
				'fieldtype': 'Code',
				'read_only': 1
			}],
			primary_action: () => {
				this.dialog.disable_primary_action();
				var params = {
					To: this.dialog.get_value('to_number')
				};

				if (this.device) {
					var outgoingConnection = this.device.connect(params);
					outgoingConnection.on("ringing", function () {
						console.log("Ringing...");
					});
				} else {
					this.dialog.enable_primary_action();
				}
			},
			primary_action_label: __('Call')
		});
		this.dialog.show();
		this.dialog.get_close_btn().show();
	}
	setup_device(access_token) {
		// Setup Twilio Device
		this.device = new Device(access_token, {
			codecPreferences: ["opus", "pcmu"],
			fakeLocalDTMF: true,
			enableRingingState: true
		});
	}

	setup_call_status_updater() {
		if (!this.updater) {
			this.updater = setInterval(this.set_call_status.bind(this), 1000);
		}
	}
	set_call_status() {
		frappe.xcall('erpnext.erpnext_integrations.exotel_integration.get_call_status', {
			'call_id': this.call_id
		}).then(status => {
			this.set_header(status);
			if (['completed', 'failed', 'busy', 'no-answer'].includes(status)) {
				this.set_call_as_complete();
			}
		}).catch(e => {
			console.log(e);
			this.set_call_as_complete();
		});
	}

	set_call_as_complete() {
		this.dialog.get_close_btn().show();
		clearInterval(this.updater);
	}

	set_header(status) {
		this.dialog.set_title(frappe.model.unscrub(status));
		const indicator_class = this.get_status_indicator(status);
		this.dialog.header.find('.indicator').attr('class', `indicator ${indicator_class}`);
	}

	get_status_indicator(status) {
		const indicator_map = {
			'completed': 'blue',
			'failed': 'red',
			'busy': 'yellow',
			'no-answer': 'orange',
			'queued': 'orange',
			'ringing': 'green blink',
			'in-progress': 'green blink'
		};
		const indicator_class = `indicator ${indicator_map[status] || 'blue blink'}`;
		return indicator_class;
	}

	get_audio_devices() {
		let selected_devices = [];

		this.device.audio.availableOutputDevices.forEach(function (device, id) {
			selected_devices.push(device);
		});
	}


}

frappe.phone_call.handler = (to_number, frm) => new TwilioCall(to_number, frm);