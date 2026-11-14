import { createApp } from "vue";
import FileUploaderComponent from "./FileUploader.vue";
import { watch } from "vue";

class FileUploader {
	static UploadOptions = [];
	constructor({
		wrapper,
		method,
		on_success,
		doctype,
		docname,
		fieldname,
		field_doctype,
		files,
		folder,
		restrictions = {},
		upload_notes,
		allow_multiple,
		as_dataurl,
		disable_file_browser,
		dialog_title,
		attach_doc_image,
		frm,
		make_attachments_public,
		allow_web_link,
		allow_take_photo,
		allow_toggle_private,
		allow_toggle_optimize,
		allow_google_drive,
		keep_grid_form_open = false,
	} = {}) {
		frm?.attachments?.max_reached?.(true);

		if (allow_toggle_private === undefined) {
			allow_toggle_private = true;
		}

		const force_private = Boolean(
			doctype && frappe.get_meta(doctype)?.force_private_attachments
		);
		if (force_private) {
			make_attachments_public = 0;
		}

		allow_toggle_private = Boolean(
			allow_toggle_private && !force_private && frappe.utils.can_upload_public_files()
		);
		this.can_toggle_private = allow_toggle_private;

		if (!wrapper) {
			this.make_dialog(dialog_title, keep_grid_form_open);
		} else {
			this.wrapper = wrapper.get ? wrapper.get(0) : wrapper;
		}

		if (restrictions && !restrictions.allowed_file_types) {
			// apply global allow list if present
			let allowed_extensions = frappe.sys_defaults?.allowed_file_extensions;
			if (allowed_extensions) {
				restrictions.allowed_file_types = allowed_extensions
					.split("\n")
					.map((ext) => `.${ext}`);
			}
		}

		let app = createApp(FileUploaderComponent, {
			show_upload_button: !Boolean(this.dialog),
			doctype,
			docname,
			fieldname,
			field_doctype,
			method,
			folder,
			on_success,
			restrictions,
			upload_notes,
			allow_multiple,
			as_dataurl,
			disable_file_browser,
			attach_doc_image,
			make_attachments_public,
			allow_web_link,
			allow_take_photo,
			allow_toggle_private,
			force_private,
			allow_toggle_optimize,
			allow_google_drive,
			additional_upload_handlers: this.constructor.UploadOptions.map((k) => ({
				...k,
				wrappedAction: () =>
					k.action({
						dialog: this.dialog,
						uploader: this.uploader,
						doctype,
						docname,
						fieldname,
					}),
			})),
		});
		SetVueGlobals(app);
		this.uploader = app.mount(this.wrapper);

		if (!this.dialog) {
			this.uploader.wrapper_ready = true;
		}

		watch(
			() => this.uploader.files,
			(files) => {
				let all_private = files.every((file) => file.private);
				if (this.dialog && this.can_toggle_private) {
					this.dialog.set_secondary_action_label(
						all_private ? __("Set all public") : __("Set all restricted")
					);
				}
			},
			{ deep: true }
		);

		watch(
			() => this.uploader.close_dialog,
			(close_dialog) => {
				if (close_dialog) {
					this.dialog && this.dialog.hide();
				}
			}
		);

		watch(
			() => this.uploader.hide_dialog_footer,
			(hide_dialog_footer) => {
				if (!this.dialog) return;
				this.dialog.footer.toggleClass("hide", hide_dialog_footer);
				this.dialog.$wrapper.data("bs.modal")._config.backdrop = hide_dialog_footer
					? "static"
					: true;
			}
		);

		if (files && files.length) {
			this.uploader.add_files(files);
		}
	}

	upload_files() {
		return this.uploader.upload_files(this.dialog);
	}

	make_dialog(title, keep_grid_form_open) {
		const dialog_opts = {
			title: title || __("Upload"),
			keep_grid_form_open,
			primary_action_label: __("Upload"),
			primary_action_loading_label: __("Uploading"),
			primary_action: () => this.upload_files(),
			on_page_show: () => {
				this.uploader.wrapper_ready = true;
			},
		};

		// Only add secondary action if user is allowed to toggle privacy
		if (this.can_toggle_private) {
			dialog_opts.secondary_action_label = __("Set all restricted");
			dialog_opts.secondary_action = () => {
				this.uploader.toggle_all_private();
			};
		}

		this.dialog = new frappe.ui.Dialog(dialog_opts);

		this.wrapper = this.dialog.body;
		this.dialog.show();
		this.dialog.$wrapper.on("hidden.bs.modal", function () {
			$(this).data("bs.modal", null);
			$(this).remove();
		});
	}
}

frappe.provide("frappe.ui");
frappe.ui.FileUploader = FileUploader;
export default FileUploader;
