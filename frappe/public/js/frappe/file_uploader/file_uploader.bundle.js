import { createApp } from "vue";
import FileUploaderComponent from "./FileUploader.vue";
import { watch } from "vue";

const parstDoctype = "Handle Parts";
let doctype_selected = "";
let parent_doctype = "";


class FileUploader {
	constructor({
		wrapper,
		method,
		on_success,
		doctype,
		docname,
		fieldname,
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
	} = {}) {
		frm && frm.attachments.max_reached(true);
		if (!wrapper) {
			this.make_dialog(dialog_title);
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
		});
		SetVueGlobals(app);
		this.uploader = app.mount(this.wrapper);

		if (!this.dialog) {
			this.uploader.wrapper_ready = true;
		}

		watch(
			() => this.uploader.files,
			(files) => {
				if (doctype == parstDoctype) {

					parent_doctype = doctype;
				} else {
					parent_doctype = "";
				}
				let all_private = files.every((file) => file.private);
				if (this.dialog) {
					this.dialog.set_secondary_action_label(
						all_private ? __("Set all public") : __("Set all private")
					);
				}
			},
			{ deep: true }
		);

		watch(
			() => this.uploader.trigger_upload,
			(trigger_upload) => {
				if (trigger_upload) {
					this.upload_files();
				}
			}
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
				if (hide_dialog_footer) {
					this.dialog && this.dialog.footer.addClass("hide");
					this.dialog.$wrapper.data("bs.modal")._config.backdrop = "static";
				} else {
					this.dialog && this.dialog.footer.removeClass("hide");
					this.dialog.$wrapper.data("bs.modal")._config.backdrop = true;
				}
			}
		);

		if (files && files.length) {
			this.uploader.add_files(files);
		}
	}

	upload_files() {
		this.dialog && this.dialog.get_primary_btn().prop("disabled", true);
		this.dialog && this.dialog.get_secondary_btn().prop("disabled", true);
		if (parent_doctype == parstDoctype) {
			const doctypeElement = document.querySelector('select.input-with-feedback');
			const selectedDoctype = doctypeElement ? doctypeElement.value : null;

			if (selectedDoctype) {
				this.uploader.files.forEach((file) => {
					const reader = new FileReader();
					reader.onload = async (event) => {
						// const binaryData = event.target.result;
						const binaryData = btoa(
							new Uint8Array(event.target.result)
								.reduce((data, byte) => data + String.fromCharCode(byte), '')
						);
						try {
							const { pre_signed_url } = await frappe.db.get_doc('Handle Parts Config');

							const response = await fetch(pre_signed_url, {
								method: 'POST',
								headers: {
									'Content-Type': 'application/json',
								},
								body: JSON.stringify({
									filename: file.file_obj.name,
									contentType: file.file_obj.type,
									doctype: selectedDoctype,
									action: "insert-item",
									user_to_notify: frappe.session.user
								}),
							});

							const value = await response.json();
							if (value.url) {
								await frappe.db.set_value("Handle Parts Config", "Handle Parts Config", {
									submit_file_url: value.url,
									date_time_url_created: frappe.datetime.now_datetime(),
									binary_data: binaryData
								});
							}
						} catch (error) {
							frappe.msgprint({
								title: __('Error'),
								message: __('Error getting pre-signed URL'),
								indicator: 'red',
								clear: true,
							});
							return
						}
					};
					reader.readAsArrayBuffer(file.file_obj);
				});
				return this.uploader.upload_files();
			} else {
				frappe.msgprint({
					title: __('Error'),
					message: __('Doctype is not selected or found.'),
					indicator: 'red',
					clear: true,
				});
				return
			}
		} else {
			return this.uploader.upload_files();
		}
	}



	make_dialog(title) {
		this.dialog = new frappe.ui.Dialog({
			title: title || __("Upload"),
			primary_action_label: __("Upload"),
			primary_action: () => this.upload_files(),
			secondary_action_label: __("Set all private"),
			secondary_action: () => {
				this.uploader.toggle_all_private();
			},
			on_page_show: () => {
				this.uploader.wrapper_ready = true;
			},
		});

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
