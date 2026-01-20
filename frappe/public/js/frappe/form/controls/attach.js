frappe.ui.form.ControlAttach = class ControlAttach extends frappe.ui.form.ControlData {
	make_input() {
		let me = this;
		this.$input = $('<button class="btn btn-default btn-xs btn-attach">')
			.html(__("Attach"))
			.prependTo(me.input_area)
			.css({
				"margin": "0",
				"vertical-align": "middle",
				"line-height": "1.5"
			})
			.on({
				click: function () {
					me.on_attach_click();
				},
				attach_doc_image: function () {
					me.on_attach_doc_image();
				},
			});
		this.$value = $(
			`<div class="attached-file flex justify-between align-center">
				<div class="ellipsis">
				${frappe.utils.icon("es-line-link", "sm")}
					<a class="attached-file-link" target="_blank"></a>
					<span class="pending-badge text-warning small" style="display:none;"> (${__("pending upload")})</span>
				</div>
				<div class="flex" style="align-items: center">
					<a class="btn btn-xs btn-default" data-action="reload_attachment">${__("Reload File")}</a>
					<a class="btn btn-xs btn-default" data-action="clear_attachment">${__("Clear")}</a>
				</div>
			</div>`
		)
			.prependTo(me.input_area)
			.toggle(false);
		this.input = this.$input.get(0);
		this.set_input_attributes();
		this.has_input = true;

		frappe.utils.bind_actions_with_object(this.$value, this);
		this.toggle_reload_button();
	}
	clear_attachment() {
		let me = this;
		frappe.confirm(__("Are you sure you want to delete the attachment?"), function () {
			if (me.frm) {
				// Clear pending file if any
				me.clear_pending_file();
				me.parse_validate_and_set_in_model(null);
				me.refresh();
				// Only remove from server if not a pending file
				if (me.value && !me.value.startsWith("pending:")) {
					me.frm.attachments.remove_attachment_by_filename(me.value, async () => {
						await me.parse_validate_and_set_in_model(null);
						me.refresh();
						me.frm.doc.docstatus == 1 ? me.frm.save("Update") : me.frm.save();
					});
				}
			} else {
				me.dataurl = null;
				me.fileobj = null;
				me.set_input(null);
				me.parse_validate_and_set_in_model(null);
				me.refresh();
			}
		});
	}
	
	clear_pending_file() {
		if (this.pending_file && this.frm && this.frm._pending_attachments) {
			this.frm._pending_attachments = this.frm._pending_attachments.filter(
				(p) => p.control !== this
			);
		}
		this.pending_file = null;
		this.$value.find(".pending-badge").hide();
	}
	
	reload_attachment() {
		if (this.file_uploader) {
			this.file_uploader.uploader.upload_files();
		}
	}
	on_attach_click() {
		// For new documents, use a file input to select locally
		if (this.frm && this.frm.doc.__islocal) {
			this.select_file_locally();
		} else {
			this.set_upload_options();
			this.file_uploader = new frappe.ui.FileUploader(this.upload_options);
		}
	}
	on_attach_doc_image() {
		this.set_upload_options();
		this.upload_options.restrictions.allowed_file_types = ["image/*"];
		this.file_uploader = new frappe.ui.FileUploader(this.upload_options);
	}
	
	select_file_locally() {
		// Create a hidden file input for local file selection
		let me = this;
		let file_input = $('<input type="file" style="display:none">');
		file_input.on("change", function () {
			if (this.files && this.files.length > 0) {
				me.store_pending_file(this.files[0]);
			}
			file_input.remove();
		});
		$("body").append(file_input);
		file_input.click();
	}
	
	store_pending_file(file) {
		// Store the File object for later upload
		this.pending_file = file;
		
		// Set a temporary value to indicate pending upload
		let display_value = `pending:${file.name}`;
		this.set_input(display_value);
		this.parse_validate_and_set_in_model(display_value);
		
		// Show pending badge
		this.$value.find(".pending-badge").show();
		
		// Register with form for deferred upload
		if (!this.frm._pending_attachments) {
			this.frm._pending_attachments = [];
		}
		
		this.frm._pending_attachments.push({
			control: this,
			fieldname: this.df.fieldname,
			file: file,
		});
	}
	
	set_upload_options() {
		let options = {
			allow_multiple: false,
			on_success: (file) => {
				this.on_upload_complete(file);
				this.toggle_reload_button();
			},
			restrictions: {},
		};

		if (this.frm) {
			options.doctype = this.frm.doctype;
			options.docname = this.frm.docname;
			options.fieldname = this.df.fieldname;
			options.make_attachments_public = this.df.make_attachment_public
				? 1
				: this.frm.meta.make_attachments_public;
		}

		if (this.df.options) {
			Object.assign(options, this.df.options);
		}
		this.upload_options = options;
	}

	set_input(value, dataurl) {
		this.last_value = this.value;
		this.value = value;
		if (this.value) {
			let filename = this.value;
			let href = this.value;
			
			// Handle pending files
			if (this.value.startsWith("pending:")) {
				filename = this.value.substring(8); // Remove "pending:" prefix
				href = "#"; // No link for pending files
			} else {
				// value can also be using this format: FILENAME,DATA_URL
				let file_url_parts = this.value.match(/^([^:]+),(.+):(.+)$/);
				if (file_url_parts) {
					filename = file_url_parts[1];
					dataurl = file_url_parts[2] + ":" + file_url_parts[3];
					href = dataurl;
				}
			}
			
			if (this.$input && this.$value) {
				this.$input.toggle(false);
				this.$value
					.toggle(true)
					.find(".attached-file-link")
					.text(filename)
					.attr("href", href);
			} else {
				this.$wrapper.html(`
					<div class="attached-file flex justify-between align-center">
						<div class="ellipsis">
							<a target="_blank"></a>
						</div>
					</div>
				`);
				this.$wrapper
					.find("a")
					.text(filename)
					.attr("href", href);
			}
		} else {
			this.$input.toggle(true);
			this.$value.toggle(false);
			this.$value.find(".pending-badge").hide();
		}
	}

	get_value() {
		return this.value || null;
	}

	async on_upload_complete(attachment) {
		if (this.frm) {
			await this.parse_validate_and_set_in_model(attachment.file_url);
			this.frm.attachments.update_attachment(attachment);
			// Don't auto-save if this is a new (unsaved) document
			if (!this.frm.doc.__islocal) {
				this.frm.doc.docstatus == 1 ? this.frm.save("Update") : this.frm.save();
			}
		}
		this.set_value(attachment.file_url);
	}

	toggle_reload_button() {
		this.$value
			.find('[data-action="reload_attachment"]')
			.toggle(this.file_uploader && this.file_uploader.uploader.files.length > 0);
	}
	
	// Upload pending file (called after document is saved)
	async upload_pending_file() {
		if (!this.pending_file || !this.frm) return;
		
		return new Promise((resolve, reject) => {
			const file = this.pending_file;
			const formData = new FormData();
			formData.append("file", file, file.name);
			formData.append("doctype", this.frm.doctype);
			formData.append("docname", this.frm.docname);
			formData.append("fieldname", this.df.fieldname);
			formData.append("folder", "Home/Attachments");
			formData.append("is_private", "1");
			formData.append("cmd", "frappe.handler.upload_file");
			
			$.ajax({
				url: "/api/method/frappe.handler.upload_file",
				type: "POST",
				data: formData,
				processData: false,
				contentType: false,
				headers: {
					"X-Frappe-CSRF-Token": frappe.csrf_token,
				},
				success: (r) => {
					if (r.message) {
						this.pending_file = null;
						this.$value.find(".pending-badge").hide();
						this.set_value(r.message.file_url);
						this.parse_validate_and_set_in_model(r.message.file_url);
						this.frm.attachments.update_attachment(r.message);
						resolve(r.message);
					} else {
						reject(new Error("Upload failed"));
					}
				},
				error: (xhr, status, error) => {
					reject(new Error(error));
				},
			});
		});
	}
};
