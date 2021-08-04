frappe.provide("frappe.ui");

frappe.ui.Scanner = class Scanner {
	constructor(options) {
		this.dialog = null;
		this.handler = null;
		this.options = options;

		if (!("multiple" in this.options)) {
			this.options.multiple = false;
		}
		if (options.container) {
			this.$scan_area = $(options.container);
			this.scan_area_id = frappe.dom.set_unique_id(this.$scan_area);
		}
		if (options.dialog) {
			this.dialog = this.make_dialog();
			this.dialog.show();
		}
	}

	scan() {
		this.load_lib().then(() => this.start_scan());
	}

	start_scan() {
		if (!this.handler) {
			this.handler = new Html5Qrcode(this.scan_area_id);
		}
		this.handler
			.start(
				{ facingMode: "environment" },
				{ fps: 10, qrbox: 250 },
				(decodedText, decodedResult) => {
					if (this.options.on_scan) {
						this.options.on_scan(decodedResult);
					}
					if (!this.options.multiple) {
						this.stop_scan();
					}
				},
				errorMessage => {
					// parse error, ignore it.
				}
			)
			.catch(err => {
				console.warn(errorMessage);
			});
	}

	stop_scan() {
		if (this.handler) {
			this.handler.stop().then(() => {
				this.$scan_area.empty();
			});
		}
	}

	make_dialog() {
		let dialog = new frappe.ui.Dialog({
			title: __("Scan QRCode"),
			fields: [
				{
					fieldtype: "HTML",
					fieldname: "scan_area"
				}
			],
			on_page_show: () => {
				this.$scan_area = dialog.get_field("scan_area").$wrapper;
				this.$scan_area.addClass("barcode-scanner");
				this.scan_area_id = frappe.dom.set_unique_id(this.$scan_area);
				this.scan();
			}
		});
		return dialog;
	}

	hide_dialog() {
		this.dialog && this.dialog.hide();
	}

	load_lib() {
		return frappe.require(
			"/assets/frappe/node_modules/html5-qrcode/dist/html5-qrcode.min.js"
		);
	}
};
