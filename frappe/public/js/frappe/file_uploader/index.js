import FileUploaderComponent from './FileUploader.vue';

export default class FileUploader {
	constructor({
		wrapper,
		method,
		on_success,
		doctype,
		docname,
		files,
		folder,
		restrictions,
		upload_notes,
		allow_multiple,
		as_dataurl,
		disable_file_browser,
	} = {}) {
		if (!wrapper) {
			this.make_dialog();
		} else {
			this.wrapper = wrapper.get ? wrapper.get(0) : wrapper;
		}

		this.$fileuploader = new Vue({
			el: this.wrapper,
			render: h => h(FileUploaderComponent, {
				props: {
					show_upload_button: !Boolean(this.dialog),
					doctype,
					docname,
					method,
					folder,
					on_success,
					restrictions,
					upload_notes,
					allow_multiple,
					as_dataurl,
					disable_file_browser,
				}
			})
		});

		this.uploader = this.$fileuploader.$children[0];

		if (files && files.length) {
			this.uploader.add_files(files);
		}
	}

	upload_files() {
		this.dialog && this.dialog.get_primary_btn().prop('disabled', true);
		return this.uploader.upload_files()
			.then(() => {
				this.dialog && this.dialog.hide();
			});
	}

	make_dialog() {
		this.dialog = new frappe.ui.Dialog({
			title: 'Upload',
			fields: [
				{
					fieldtype: 'HTML',
					fieldname: 'upload_area'
				}
			],
			primary_action_label: __('Upload'),
			primary_action: () => this.upload_files()
		});

		this.wrapper = this.dialog.fields_dict.upload_area.$wrapper[0];
		this.dialog.show();
		this.dialog.$wrapper.on('hidden.bs.modal', function() {
			$(this).data('bs.modal', null);
			$(this).remove();
		});
	}
}
