frappe.ui.form.ControlAttach = frappe.ui.form.ControlData.extend({
	make_input: function() {
		let me = this;
		this.$input = $('<button class="btn btn-default btn-sm btn-attach">')
			.html(__("Attach"))
			.prependTo(me.input_area)
			.on("click", function() {
				me.on_attach_click();
			});
		this.$value = $(
			`<div class="attached-file flex justify-between align-center">
				<div class="ellipsis">
					<i class="fa fa-paperclip"></i>
					<a class="attached-file-link" target="_blank"></a>
				</div>
				<div>
					<a class="btn btn-xs btn-default" data-action="reload_attachment">${__('Reload File')}</a>
					<a class="btn btn-xs btn-default" data-action="clear_attachment">${__('Clear')}</a>
				</div>
			</div>`)
			.prependTo(me.input_area)
			.toggle(false);
		this.input = this.$input.get(0);
		this.set_input_attributes();
		this.has_input = true;

		frappe.utils.bind_actions_with_object(this.$value, this);
		this.toggle_reload_button();
	},
	clear_attachment: function() {
		let me = this;
		if(this.frm) {
			me.parse_validate_and_set_in_model(null);
			me.refresh();
			me.frm.attachments.remove_attachment_by_filename(me.value, async function() {
				await me.parse_validate_and_set_in_model(null);
				me.refresh();
				me.frm.doc.docstatus == 1 ? me.frm.save('Update') : me.frm.save();
			});
		} else {
			this.dataurl = null;
			this.fileobj = null;
			this.set_input(null);
			this.parse_validate_and_set_in_model(null);
			this.refresh();
		}
	},
	reload_attachment() {
		if (this.file_uploader) {
			this.file_uploader.uploader.upload_files();
		}
	},
	on_attach_click() {
		this.set_upload_options();
		this.file_uploader = new frappe.ui.FileUploader(this.upload_options);
	},
	set_upload_options() {
		let options = {
			allow_multiple: false,
			on_success: file => {
				this.on_upload_complete(file);
				this.toggle_reload_button();
			}
		};

		if (this.frm) {
			options.doctype = this.frm.doctype;
			options.docname = this.frm.docname;
			options.fieldname = this.grid ? this.grid.df.fieldname : this.df.fieldname;
			options.make_attachments_public = this.frm.meta.make_attachments_public;
		}

		if (this.df.options) {
			Object.assign(options, this.df.options);
		}
		this.upload_options = options;
	},

	set_input: function(value, dataurl) {
		this.last_value = this.value;
		this.value = value;
		if (this.value) {
			this.$input.toggle(false);
			// value can also be using this format: FILENAME,DATA_URL
			// Important: We have to be careful because normal filenames may also contain ","
			let file_url_parts = this.value.match(/^([^:]+),(.+):(.+)$/);
			let filename;
			if (file_url_parts) {
				filename = file_url_parts[1];
				dataurl = file_url_parts[2] + ':' + file_url_parts[3];
			}
			this.$value.toggle(true).find(".attached-file-link")
				.html(filename || this.value)
				.attr("href", dataurl || this.value);
		} else {
			this.$input.toggle(true);
			this.$value.toggle(false);
		}
	},

	get_value: function() {
		return this.value || null;
	},

	on_upload_complete: async function(attachment) {
		if(this.frm) {
			await this.parse_validate_and_set_in_model(attachment.file_url);
			this.frm.attachments.update_attachment(attachment);
			this.frm.doc.docstatus == 1 ? this.frm.save('Update') : this.frm.save();
		}
		this.set_value(attachment.file_url);
	},

	toggle_reload_button() {
		this.$value.find('[data-action="reload_attachment"]')
			.toggle(this.file_uploader && this.file_uploader.uploader.files.length > 0);
	}
});
