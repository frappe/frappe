frappe.ui.form.ControlAttach = frappe.ui.form.ControlData.extend({
	make_input: function() {
		var me = this;
		this.$input = $('<button class="btn btn-default btn-sm btn-attach">')
			.html(__("Attach"))
			.prependTo(me.input_area)
			.on("click", function() {
				me.onclick();
			});
		this.$value = $('<div style="margin-top: 5px;">\
			<div class="ellipsis" style="display: inline-block; width: 90%;">\
				<i class="fa fa-paperclip"></i> \
				<a class="attached-file" target="_blank"></a>\
			</div>\
			<a class="close" style="position: absolute; right: 15px;">&times;</a></div>')
			.prependTo(me.input_area)
			.toggle(false);
		this.input = this.$input.get(0);
		this.set_input_attributes();
		this.has_input = true;

		this.$value.find(".close").on("click", function() {
			me.clear_attachment();
		});
	},
	clear_attachment: function() {
		var me = this;
		if(this.frm) {
			me.frm.attachments.remove_attachment_by_filename(me.value, function() {
				me.parse_validate_and_set_in_model(null);
				me.refresh();
				me.frm.save();
			});
		} else {
			this.dataurl = null;
			this.fileobj = null;
			this.set_input(null);
			this.refresh();
		}
	},
	onclick: function() {
		var me = this;
		if(this.doc) {
			var doc = this.doc.parent && frappe.model.get_doc(this.doc.parenttype, this.doc.parent) || this.doc;
			if (doc.__islocal) {
				frappe.msgprint(__("Please save the document before uploading."));
				return;
			}
		}
		if(!this.dialog) {
			this.dialog = new frappe.ui.Dialog({
				title: __(this.df.label || __("Upload")),
				fields: [
					{fieldtype:"HTML", fieldname:"upload_area"},
					{fieldtype:"HTML", fieldname:"or_attach", options: __("Or")},
					{fieldtype:"Select", fieldname:"select", label:__("Select from existing attachments") },
					{fieldtype:"Button", fieldname:"clear",
						label:__("Clear Attachment"), click: function() {
							me.clear_attachment();
							me.dialog.hide();
						}
					},
				]
			});
		}

		this.dialog.show();

		this.dialog.get_field("upload_area").$wrapper.empty();

		// select from existing attachments
		var attachments = this.frm && this.frm.attachments.get_attachments() || [];
		var select = this.dialog.get_field("select");
		if(attachments.length) {
			attachments = $.map(attachments, function(o) { return o.file_url; });
			select.df.options = [""].concat(attachments);
			select.toggle(true);
			this.dialog.get_field("or_attach").toggle(true);
			select.refresh();
		} else {
			this.dialog.get_field("or_attach").toggle(false);
			select.toggle(false);
		}
		select.$input.val("");

		// show button if attachment exists
		this.dialog.get_field('clear').$wrapper.toggle(this.get_model_value() ? true : false);

		this.set_upload_options();
		frappe.upload.make(this.upload_options);
	},

	set_upload_options: function() {
		var me = this;
		this.upload_options = {
			parent: this.dialog.get_field("upload_area").$wrapper,
			args: {},
			allow_multiple: 0,
			max_width: this.df.max_width,
			max_height: this.df.max_height,
			options: this.df.options,
			btn: this.dialog.set_primary_action(__("Upload")),
			on_no_attach: function() {
				// if no attachmemts,
				// check if something is selected
				var selected = me.dialog.get_field("select").get_value();
				if(selected) {
					me.parse_validate_and_set_in_model(selected);
					me.dialog.hide();
					me.frm.save();
				} else {
					frappe.msgprint(__("Please attach a file or set a URL"));
				}
			},
			callback: function(attachment) {
				me.on_upload_complete(attachment);
				me.dialog.hide();
			},
			onerror: function() {
				me.dialog.hide();
			}
		};

		if ("is_private" in this.df) {
			this.upload_options.is_private = this.df.is_private;
		}

		if(this.frm) {
			this.upload_options.args = {
				from_form: 1,
				doctype: this.frm.doctype,
				docname: this.frm.docname
			};
		} else {
			this.upload_options.on_attach = function(fileobj, dataurl) {
				me.dialog.hide();
				me.fileobj = fileobj;
				me.dataurl = dataurl;
				if(me.on_attach) {
					me.on_attach();
				}
				if(me.df.on_attach) {
					me.df.on_attach(fileobj, dataurl);
				}
				me.on_upload_complete();
			};
		}
	},

	set_input: function(value, dataurl) {
		this.value = value;
		if(this.value) {
			this.$input.toggle(false);
			if(this.value.indexOf(",")!==-1) {
				var parts = this.value.split(",");
				var filename = parts[0];
				dataurl = parts[1];
			}
			this.$value.toggle(true).find(".attached-file")
				.html(filename || this.value)
				.attr("href", dataurl || this.value);
		} else {
			this.$input.toggle(true);
			this.$value.toggle(false);
		}
	},

	get_value: function() {
		if(this.frm) {
			return this.value;
		} else {
			if ( this.fileobj ) {
				if ( this.fileobj.file_url ) {
					return this.fileobj.file_url;
				} else if ( this.fileobj.filename ) {
					var dataURI = this.fileobj.filename + ',' + this.dataurl;

					return dataURI;
				}
			}

			return null;
		}
	},

	on_upload_complete: function(attachment) {
		if(this.frm) {
			this.parse_validate_and_set_in_model(attachment.file_url);
			this.refresh();
			this.frm.attachments.update_attachment(attachment);
			this.frm.save();
		} else {
			this.value = this.get_value();
			this.refresh();
			frappe.hide_progress();
		}
	},
});
