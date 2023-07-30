// frappe.ui.Capture
// Author - Achilles Rasquinha <achilles@frappe.io>

/**
 * @description Converts a canvas, image or a video to a data URL string.
 *
 * @param 	{HTMLElement} element - canvas, img or video.
 * @returns {string} 			  - The data URL string.
 *
 * @example
 * frappe._.get_data_uri(video)
 * // returns "data:image/pngbase64,..."
 */
frappe._.get_data_uri = (element) => {
	const width = element.videoWidth;
	const height = element.videoHeight;

	const $canvas = $("<canvas/>");
	$canvas[0].width = width;
	$canvas[0].height = height;

	const context = $canvas[0].getContext("2d");
	context.drawImage(element, 0, 0, width, height);

	const data_uri = $canvas[0].toDataURL("image/png");

	return data_uri;
};

function get_file_input() {
	let input = document.createElement("input");
	input.setAttribute("type", "file");
	input.setAttribute("accept", "image/*");
	input.setAttribute("multiple", "");

	return input;
}

function read(file) {
	return new Promise((resolve, reject) => {
		const reader = new FileReader();
		reader.onload = () => resolve(reader.result);
		reader.onerror = reject;
		reader.readAsDataURL(file);
	});
}

/**
 * @description Frappe's Capture object.
 *
 * @example
 * const capture = frappe.ui.Capture()
 * capture.show()
 *
 * capture.click((data_uri) => {
 * 	// do stuff
 * })
 *
 * @see https://developer.mozilla.org/en-US/docs/Web/API/WebRTC_API/Taking_still_photos
 */
frappe.ui.Capture = class {
	constructor(options = {}) {
		this.options = frappe.ui.Capture.OPTIONS;
		this.set_options(options);

		this.facing_mode = "environment";
		this.images = [];
	}

	set_options(options) {
		this.options = { ...frappe.ui.Capture.OPTIONS, ...options };

		return this;
	}

	show() {
		this.build_dialog();

		if (cint(frappe.boot.sysdefaults.force_web_capture_mode_for_uploads)) {
			this.show_for_desktop();
		} else if (frappe.is_mobile()) {
			this.show_for_mobile();
		} else {
			this.show_for_desktop();
		}
	}

	build_dialog() {
		let me = this;
		me.dialog = new frappe.ui.Dialog({
			title: this.options.title,
			animate: this.options.animate,
			fields: [
				{
					fieldtype: "HTML",
					fieldname: "capture",
				},
				{
					fieldtype: "HTML",
					fieldname: "total_count",
				},
			],
			on_hide: this.stop_media_stream(),
		});

		me.$template = $(frappe.ui.Capture.TEMPLATE);

		let field = me.dialog.get_field("capture");
		$(field.wrapper).html(me.$template);

		me.dialog.get_close_btn().on("click", () => {
			me.hide();
		});
	}

	show_for_mobile() {
		let me = this;
		if (!me.input) {
			me.input = get_file_input();
		}

		me.input.onchange = async () => {
			for (let file of me.input.files) {
				let f = await read(file);
				me.images.push(f);
			}

			me.render_preview();
			me.dialog.show();
		};
		me.input.click();
	}

	show_for_desktop() {
		let me = this;

		this.render_stream()
			.then(() => {
				me.dialog.show();
			})
			.catch((err) => {
				if (me.options.error) {
					frappe.show_alert(frappe.ui.Capture.ERR_MESSAGE, 3);
				}

				throw err;
			});
	}

	render_stream() {
		let me = this;
		let constraints = {
			video: {
				facingMode: this.facing_mode,
			},
		};

		return navigator.mediaDevices.getUserMedia(constraints).then((stream) => {
			me.stream = stream;
			me.dialog.custom_actions.empty();
			me.dialog.get_primary_btn().off("click");
			me.setup_take_photo_action();
			me.setup_preview_action();
			me.setup_toggle_camera();

			me.$template.find(".fc-stream-container").show();
			me.$template.find(".fc-preview-container").hide();
			me.video = me.$template.find("video")[0];
			me.video.srcObject = me.stream;
			me.video.load();
			me.video.play();
		});
	}

	render_preview() {
		this.stop_media_stream();
		this.$template.find(".fc-stream-container").hide();
		this.$template.find(".fc-preview-container").show();
		this.dialog.get_primary_btn().off("click");

		let images = ``;

		this.images.forEach((image, idx) => {
			images += `
				<div class="mt-1 p-1 rounded col-md-3 col-sm-4 col-xs-4" data-idx="${idx}">
					<span class="capture-remove-btn" data-idx="${idx}">
						${frappe.utils.icon("close", "lg")}
					</span>
					<img class="rounded" src="${image}" data-idx="${idx}">
				</div>
			`;
		});

		this.$template.find(".fc-preview-container").empty();
		$(this.$template.find(".fc-preview-container")).html(
			`<div class="row">
				${images}
			</div>`
		);

		this.setup_capture_action();
		this.setup_submit_action();
		this.setup_remove_action();
		this.update_count();
		this.dialog.custom_actions.empty();
	}

	setup_take_photo_action() {
		let me = this;

		this.dialog.set_primary_action(__("Take Photo"), () => {
			const data_url = frappe._.get_data_uri(me.video);

			me.images.push(data_url);
			me.setup_preview_action();
			me.update_count();
		});
	}

	setup_preview_action() {
		let me = this;

		if (!this.images.length) {
			return;
		}

		this.dialog.set_secondary_action_label(__("Preview"));
		this.dialog.set_secondary_action(() => {
			me.dialog.get_primary_btn().off("click");
			me.render_preview();
		});
	}

	setup_remove_action() {
		let me = this;
		let elements = this.$template[0].getElementsByClassName("capture-remove-btn");

		elements.forEach((el) => {
			el.onclick = () => {
				let idx = parseInt(el.getAttribute("data-idx"));

				me.images.splice(idx, 1);
				me.render_preview();
			};
		});
	}

	update_count() {
		let field = this.dialog.get_field("total_count");
		let msg = `${__("Total Images")}: <b>${this.images.length}`;

		if (this.images.length === 0) {
			msg = __("No Images");
		}

		$(field.wrapper).html(`
			<div class="row mt-2">
				<div class="offset-4 col-4 d-flex justify-content-center">${msg}</b></div>
			</div>
		`);
	}

	setup_toggle_camera() {
		let me = this;

		this.dialog.add_custom_action(
			__("Switch Camera"),
			() => {
				me.facing_mode = me.facing_mode == "environment" ? "user" : "environment";

				frappe.show_alert({
					message: __("Switching Camera"),
				});

				me.stop_media_stream();
				me.render_stream();
			},
			"btn-switch"
		);
	}

	setup_capture_action() {
		let me = this;

		this.dialog.set_secondary_action_label(__("Capture"));
		this.dialog.set_secondary_action(() => {
			if (frappe.is_mobile()) {
				me.show_for_mobile();
			} else {
				me.render_stream();
			}
		});
	}

	setup_submit_action() {
		let me = this;

		this.dialog.set_primary_action(__("Submit"), () => {
			me.hide();

			if (me.callback) {
				me.callback(me.images);
			}
		});
	}

	hide() {
		if (this.dialog) this.dialog.hide();
		this.stop_media_stream();
	}

	stop_media_stream() {
		if (this.stream) {
			this.stream.getTracks().forEach((track) => {
				track.stop();
			});
		}
	}

	submit(fn) {
		this.callback = fn;
	}
};
frappe.ui.Capture.OPTIONS = {
	title: __("Camera"),
	animate: false,
	error: false,
};
frappe.ui.Capture.ERR_MESSAGE = __("Unable to load camera.");
frappe.ui.Capture.TEMPLATE = `
<div class="frappe-capture">
	<div class="embed-responsive embed-responsive-16by9 fc-stream-container">
		<video class="fc-stream embed-responsive-item">${frappe.ui.Capture.ERR_MESSAGE}</video>
	</div>
	<div class="fc-preview-container px-2" style="display: none;">

	</div>
</div>
`;
