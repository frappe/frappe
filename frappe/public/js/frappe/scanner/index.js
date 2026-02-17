frappe.provide("frappe.ui");

frappe.ui.Scanner = class Scanner {
	constructor(options) {
		this.dialog = null;
		this.handler = null;
		this.options = options;
		this.is_alive = false;
		this.torch_enabled = false;

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
			this.handler = new Html5Qrcode(this.scan_area_id); // eslint-disable-line
		}
		this.handler
			.start(
				{ facingMode: "environment" },
				{ fps: 10, qrbox: 250 },
				(decodedText, decodedResult) => {
					if (this.options.on_scan) {
						try {
							this.options.on_scan(decodedResult);
						} catch (error) {
							console.error(error);
						}
					}
					if (!this.options.multiple) {
						this.stop_scan();
						this.hide_dialog();
					}
				},
				(errorMessage) => {
					// parse error, ignore it.
				}
			)
			.then(() => {
				// Check if torch is supported after camera starts
				this.check_torch_support();
			})
			.catch((err) => {
				this.is_alive = false;
				this.hide_dialog();
				console.error(err);
			});
		this.is_alive = true;
	}

	check_torch_support() {
		try {
			const capabilities = this.handler.getRunningTrackCameraCapabilities();
			if (capabilities.torchFeature && capabilities.torchFeature().isSupported()) {
				this.show_torch_button();
			}
		} catch (error) {
			// Torch not supported, silently ignore
			console.debug("Torch feature not supported on this device");
		}
	}

	show_torch_button() {
		if (!this.$torch_button) {
			this.$torch_button = $(`
				<button class="btn btn-default torch-button" 
					style="position: absolute; bottom: 20px; right: 20px; z-index: 1000;">
					<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
						<path d="M9 2h6l3 7H6l3-7z"/>
						<path d="M12 9v13"/>
						<path d="M8 22h8"/>
					</svg>
					${__("Torch")}
				</button>
			`);

			this.$torch_button.on("click", () => {
				this.toggle_torch();
			});

			this.$scan_area.css("position", "relative");
			this.$scan_area.append(this.$torch_button);
		}
	}

	toggle_torch() {
		if (!this.handler || !this.is_alive) {
			return;
		}

		this.torch_enabled = !this.torch_enabled;

		this.handler
			.applyVideoConstraints({
				advanced: [{ torch: this.torch_enabled }],
			})
			.then(() => {
				// Update button state
				this.$torch_button.toggleClass("btn-primary", this.torch_enabled);
				this.$torch_button.toggleClass("btn-default", !this.torch_enabled);
			})
			.catch((error) => {
				console.error("Failed to toggle torch:", error);
				frappe.msgprint({
					title: __("Torch Error"),
					indicator: "red",
					message: __("Unable to control torch on this device"),
				});
				// Revert state on failure
				this.torch_enabled = !this.torch_enabled;
			});
	}

	stop_scan() {
		if (this.handler && this.is_alive) {
			this.handler.stop().then(() => {
				this.is_alive = false;
				this.torch_enabled = false;
				this.$scan_area.empty();
				this.hide_dialog();
			});
		}
	}

	make_dialog() {
		let dialog = new frappe.ui.Dialog({
			title: __("Scan QRCode"),
			fields: [
				{
					fieldtype: "HTML",
					fieldname: "scan_area",
				},
			],
			on_page_show: () => {
				this.$scan_area = dialog.get_field("scan_area").$wrapper;
				this.$scan_area.addClass("barcode-scanner");
				this.scan_area_id = frappe.dom.set_unique_id(this.$scan_area);
				this.scan();
			},
			on_hide: () => {
				this.stop_scan();
			},
			minimizable: this.options.minimizable,
			primary_action_label: this.options.primary_action_label,
			primary_action: this.options.primary_action,
		});
		return dialog;
	}

	hide_dialog() {
		this.dialog && this.dialog.hide();
	}

	load_lib() {
		return frappe.require("/assets/frappe/node_modules/html5-qrcode/html5-qrcode.min.js");
	}
};
