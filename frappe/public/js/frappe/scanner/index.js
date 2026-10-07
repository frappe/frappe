frappe.provide("frappe.ui");

frappe.ui.Scanner = class Scanner {
	constructor(options) {
		this.dialog = null;
		this.handler = null;
		this.options = options;
		this.is_alive = false;
		this.track = null;
		this.audio_ctx = null;
		this.last_scan = null;
		this.stop_requested = false;
		this.allow_keep_open =
			"allow_keep_open" in options ? !!options.allow_keep_open : !!options.dialog;
		this.keep_open = this.allow_keep_open && localStorage.getItem("scanner_keep_open") === "1";

		if (!("multiple" in this.options)) {
			this.options.multiple = false;
		}
		if (options.container) {
			this.$scan_area = $(options.container);
		}
		if (options.dialog) {
			this.dialog = this.make_dialog();
			this.dialog.show();
		}
	}

	scan() {
		this.prepare_scan_area();
		this.load_lib().then(() => this.start_scan());
	}

	prepare_scan_area() {
		if (this.handler && this.is_alive) {
			this.handler.stop().catch(() => {});
			this.is_alive = false;
		}
		this.$scan_area.empty();
		this.$camera_area = $('<div class="scanner-camera"></div>').appendTo(this.$scan_area);
		this.scan_area_id = frappe.dom.set_unique_id(this.$camera_area);
		this.handler = null;
	}

	start_scan() {
		if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
			this.show_error(
				__(
					"Camera access needs a secure (HTTPS) connection and a browser with camera support."
				)
			);
			return;
		}
		if (!this.handler) {
			this.handler = new Html5Qrcode(this.scan_area_id); // eslint-disable-line
		}
		this.stop_requested = false;
		this.handler
			.start(
				{ facingMode: "environment" },
				{ fps: 10, qrbox: 250 },
				(decodedText, decodedResult) => this.on_scan_success(decodedText, decodedResult),
				(errorMessage) => {
					// parse error, ignore it.
				}
			)
			.then(() => {
				this.is_alive = true;
				if (this.stop_requested) {
					// dialog was closed while the camera was still starting up
					this.stop_scan();
					return;
				}
				this.setup_enhancements();
			})
			.catch((err) => {
				this.is_alive = false;
				this.show_error(err);
			});
	}

	show_error(error) {
		console.error(error);
		this.inject_style();
		let message = typeof error === "string" ? error : error && error.message;
		if (error && error.name === "NotAllowedError") {
			message = __(
				"Camera permission was denied. Allow camera access in your browser settings and try again."
			);
		}
		this.$scan_area &&
			this.$scan_area.html(
				`<div class="scanner-error text-muted">${frappe.utils.escape_html(
					message || __("Could not start the camera.")
				)}</div>`
			);
	}

	on_scan_success(decodedText, decodedResult) {
		const is_new = !this.is_duplicate(decodedText);
		// multiple mode keeps the pre-existing contract of reporting every frame;
		// the dedupe only gates the scan feedback there
		if (!is_new && !this.options.multiple) return;
		if (is_new) {
			navigator.vibrate && navigator.vibrate(80);
			this.scan_feedback();
		}
		if (this.options.on_scan) {
			try {
				this.options.on_scan(decodedResult);
			} catch (error) {
				console.error(error);
			}
		}
		if (!this.options.multiple && !this.keep_open) {
			this.stop_scan();
			this.hide_dialog();
		}
	}

	is_duplicate(text) {
		const now = Date.now();
		if (this.last_scan && this.last_scan.text === text && now - this.last_scan.at < 2000) {
			this.last_scan.at = now;
			return true;
		}
		this.last_scan = { text, at: now };
		return false;
	}

	setup_enhancements() {
		this.inject_style();
		const video = this.$camera_area.find("video").get(0);
		this.track = video && video.srcObject ? video.srcObject.getVideoTracks()[0] : null;
		this.$controls = $('<div class="scanner-controls"></div>').appendTo(this.$scan_area);
		this.render_zoom_control();
		this.render_torch_button(3);
		this.render_keep_open_toggle();
	}

	get_capabilities() {
		try {
			return this.track && this.track.getCapabilities ? this.track.getCapabilities() : {};
		} catch (e) {
			return {};
		}
	}

	render_zoom_control() {
		const caps = this.get_capabilities();
		if (!this.track || !caps.zoom) return;
		const settings = this.track.getSettings ? this.track.getSettings() : {};
		const $zoom = $(`
			<label class="scanner-zoom">
				<span class="text-muted">${__("Zoom")}</span>
				<input type="range" min="${caps.zoom.min}" max="${caps.zoom.max}"
					step="${caps.zoom.step || 0.1}" value="${settings.zoom || caps.zoom.min}" />
			</label>
		`);
		$zoom.find("input").on("input", (e) => {
			this.track
				.applyConstraints({ advanced: [{ zoom: Number(e.target.value) }] })
				.catch(() => {});
		});
		this.$controls.append($zoom);
	}

	render_torch_button(retries) {
		if (!this.track || !this.is_alive) return;
		if (!this.get_capabilities().torch) {
			// some Android browsers report the torch capability only after the
			// track has been live for a moment
			retries > 0 && setTimeout(() => this.render_torch_button(retries - 1), 500);
			return;
		}
		let torch_on = false;
		const $torch = $(`
			<button type="button" class="scanner-torch" title="${__("Toggle Flash")}">
				<svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor">
					<path d="M7 2v11h3v9l7-12h-4l4-8H7z"/>
				</svg>
			</button>
		`);
		$torch.on("click", () => {
			torch_on = !torch_on;
			$torch.toggleClass("active", torch_on);
			this.track.applyConstraints({ advanced: [{ torch: torch_on }] }).catch(() => {});
		});
		this.$camera_area.append($torch);
	}

	render_keep_open_toggle() {
		if (!this.allow_keep_open || this.options.multiple) return;
		const $toggle = $(`
			<label class="scanner-keep-open">
				<input type="checkbox" ${this.keep_open ? "checked" : ""} />
				<span>${__("Keep scanner open after scan")}</span>
			</label>
		`);
		$toggle.find("input").on("change", (e) => {
			this.keep_open = e.target.checked;
			localStorage.setItem("scanner_keep_open", e.target.checked ? "1" : "0");
		});
		this.$scan_area.append($toggle);
	}

	scan_feedback() {
		this.play_beep();
		if (this.$camera_area) {
			const $flash = $('<div class="scanner-flash"></div>').appendTo(this.$camera_area);
			setTimeout(() => $flash.remove(), 400);
		}
	}

	play_beep() {
		try {
			const Ctx = window.AudioContext || window.webkitAudioContext;
			if (!Ctx) return;
			this.audio_ctx = this.audio_ctx || new Ctx();
			this.audio_ctx.state === "suspended" && this.audio_ctx.resume();
			const now = this.audio_ctx.currentTime;
			const osc = this.audio_ctx.createOscillator();
			const gain = this.audio_ctx.createGain();
			osc.type = "sine";
			osc.frequency.value = 1660;
			gain.gain.setValueAtTime(0.2, now);
			gain.gain.exponentialRampToValueAtTime(0.001, now + 0.15);
			osc.connect(gain).connect(this.audio_ctx.destination);
			osc.start(now);
			osc.stop(now + 0.15);
		} catch (e) {
			// audio feedback is best-effort
		}
	}

	inject_style() {
		if (document.getElementById("frappe-barcode-scanner-style")) return;
		const style = document.createElement("style");
		style.id = "frappe-barcode-scanner-style";
		style.textContent = `
			.barcode-scanner .scanner-camera { position: relative; overflow: hidden; border-radius: var(--border-radius-md, 8px); }
			.barcode-scanner .scanner-torch { position: absolute; top: 10px; right: 10px; width: 40px; height: 40px; padding: 0; border: none; border-radius: 50%; background: rgba(0, 0, 0, 0.5); color: #fff; display: flex; align-items: center; justify-content: center; cursor: pointer; z-index: 5; }
			.barcode-scanner .scanner-torch.active { background: #fff; color: #f59e0b; }
			.barcode-scanner .scanner-flash { position: absolute; inset: 0; background: rgba(255, 255, 255, 0.85); animation: scanner-flash-fade 0.4s ease-out forwards; pointer-events: none; z-index: 6; }
			@keyframes scanner-flash-fade { from { opacity: 1; } to { opacity: 0; } }
			.barcode-scanner .scanner-controls { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; margin-top: 10px; }
			.barcode-scanner .scanner-zoom { display: flex; align-items: center; gap: 8px; flex: 1; min-width: 140px; margin: 0; }
			.barcode-scanner .scanner-zoom input { width: 100%; }
			.barcode-scanner .scanner-keep-open { display: flex; align-items: center; gap: 8px; margin: 10px 0 0; cursor: pointer; font-size: var(--text-sm, 12px); color: var(--text-muted); }
			.barcode-scanner .scanner-keep-open input { margin: 0; }
			.barcode-scanner .scanner-error { padding: 40px 15px; text-align: center; }
		`;
		document.head.appendChild(style);
	}

	stop_scan() {
		this.stop_requested = true;
		if (this.audio_ctx) {
			this.audio_ctx.close().catch(() => {});
			this.audio_ctx = null;
		}
		this.track = null;
		if (this.handler && this.is_alive) {
			this.handler.stop().then(() => {
				this.is_alive = false;
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
