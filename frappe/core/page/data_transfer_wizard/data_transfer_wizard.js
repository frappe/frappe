
frappe.DataTransferWizard = Class.extend({
	init: function(parent) {
		var me =this;
		this.page = frappe.ui.make_app_page({
			parent: parent,
			title: __("Data Transfer Wizard"),
			single_column: true
		});
		this.page.add_menu_item(__("Export"), function() {
			me.show_export();
		});
		this.page.add_menu_item(__("Import"), function() {	
			me.show_import();
		});
		this.make();
		this.make_upload();
		this.make_import();
	},
	
	make: function() {
		var me = this;
		frappe.boot.user.can_import = frappe.boot.user.can_import.sort();
		$(frappe.render_template("data_transfer_wizard", this)).appendTo(this.page.main);
		this.select = this.page.main.find("select.doctype");
		this.select.on("change", function() {
			me.doctype = $(this).val();
			me.page.main.find(".select-file").removeClass("hide");
			frappe.model.with_doctype(me.doctype, function() {
				if(me.doctype) {
				}
			});
			
		});			
		
	},

	make_upload: function() {
		var me = this;
		frappe.upload.make({
			parent: this.page.main.find(".upload-area"),
			btn: this.page.main.find(".btn-upload"),
			args: {
				method: 'frappe.core.page.data_transfer_wizard.import_tool.upload_data',
			},
		
			callback: function(r) {
				var selected_doctype = frappe.get_doc('DocType', me.doctype);
				me.page.main.find(".imported-data").removeClass("hide");
				me.imported_data = me.page.main.find(".imported-data-row");
				$(frappe.render_template("try_html", {imported_data: r, fields:selected_doctype.fields}))
										.appendTo(me.imported_data.empty());
				me.select_row_no = me.page.main.find("select.row-no");
				me.select_row_no.on("change", function() {
					me.row_no = $(this).val();
					console.log(me.row_no);
				});
				me.select_column = me.page.main.find("select.col-1");
				me.select_column.on("change", function() {
					me.column = $(this).val();
					console.log(me.column);
				});
	
			},
			is_private: true
		});

		frappe.realtime.on("data_import_progress", function(data) {
			if(data.progress) {
				frappe.hide_msgprint(true);
				me.has_progress = true;
				frappe.show_progress(__("Importing"), data.progress[0],
					data.progress[1]);
			}
		})
	},
	
	make_import: function() {
		var me = this;
			
		frappe.upload.make({
			//parent: this.page.main.find(".upload-the-data"),
			btn: this.page.main.find(".btn-import"),
			get_params: function() {
				return {
					submit_after_import: me.page.main.find('[name="submit_after_import"]').prop("checked"),
					ignore_encoding_errors: me.page.main.find('[name="ignore_encoding_errors"]').prop("checked"),
					overwrite: !me.page.main.find('[name="always_insert"]').prop("checked"),
					no_email: me.page.main.find('[name="no_email"]').prop("checked")
				}
			},
			args: {
				method: 'frappe.core.page.data_transfer_wizard.import_tool.import_data',
			},
			callback: function(r) {
				var selected_doctype = frappe.get_doc('DocType', me.doctype);
				me.page.main.find(".imported-data").removeClass("hide");
				me.imported_data = me.page.main.find(".imported-data-row");
	
			},
		});
	},
	
	// write_data: function(data) {
	// 	this.page.main.find(".imported-data").removeClass("hide");
	// 	var parent = this.page.main.find(".imported-data-row").empty();

	// 	// TODO render using template!
	// 	for (var i=0, l=data.length; i<l; i++) {
	// 		var v = data[i];
	// 		console.log(v)
	// 		frappe.render_template("try_html", {doctype: doctype_list}).appendTo(parent);
	// 	}
	// }
	
});


frappe.pages['data-transfer-wizard'].on_page_load = function(wrapper) {
	frappe.data_transfer_wizard = new frappe.DataTransferWizard(wrapper);
}


frappe.pages['data-transfer-wizard'].on_page_show = function(wrapper) {
	frappe.data_transfer_wizard; //&& frappe.data_transfer_wizard.set_route_options();
}