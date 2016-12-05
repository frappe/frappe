
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
	},
	
	make: function() {
		var me = this;
		frappe.boot.user.can_import = frappe.boot.user.can_import.sort();
		$(frappe.render_template("data_transfer_wizard", this)).appendTo(this.page.main);
		this.select = this.page.main.find("select.doctype");
		this.select_column = this.page.main.find(".doctype-column")
		this.select.on("change", function() {
			me.doctype = $(this).val();
			console.log(me.doctype);
			frappe.model.with_doctype(me.doctype, function() {
				if(me.doctype) {
					// render select columns
					
					// for (var i = 0; i < selected_doctype.fields.length; i++) {
					// 		console.log(selected_doctype.fields[i]);
						
					// }
					// selected_doctype["reqd"] = true;
					// var doctype_list = [selected_doctype];

					// $(frappe.render_template("try_html", {doctype: doctype_list}))
					// 	.appendTo(me.doctype-column.empty());
				}
			});
			
		});			
		
	},
	make_upload: function() {
		var me = this;
		frappe.upload.make({
			parent: this.page.main.find(".upload-area"),
			btn: this.page.main.find(".btn-import"),
			args: {
				method: 'frappe.core.page.data_transfer_wizard.import_tool.upload',
			},
		
			callback: function(r) {
				// console.log(r)
				// console.log(me)
				// r.messages = ["<h5 style='color:green'>" + __("Import Successful!") + "</h5>"].
				// 	concat(r.message.messages)
				// me.write_data(r);
				var selected_doctype = frappe.get_doc('DocType', me.doctype);
				me.page.main.find(".imported-data").removeClass("hide");
				me.imported_data = me.page.main.find(".imported-data-row");
				// for (var i = 0; i < r.length; i++) {
				// 	for (var j = 0; j < r[i].length; j++) {
				// 		console.log(r[i][j]);
				// 	}
				// }
				$(frappe.render_template("try_html", {imported_data: r, fields:selected_doctype.fields})).appendTo(me.imported_data.empty());
	
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

	}
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