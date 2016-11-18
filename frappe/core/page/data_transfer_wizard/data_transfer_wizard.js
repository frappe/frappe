
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
		//this.make_upload();
	},
	// set_route_options: function() {
	// 	var doctype = null;
	// 	if(frappe.get_route()[1]) {
	// 		doctype = frappe.get_route()[1];
	// 	} else if(frappe.route_options && frappe.route_options.doctype) {
	// 		doctype = frappe.route_options.doctype;
	// 	}
	// 	if(in_list(frappe.boot.user.can_import, doctype)) {
	// 			this.select.val(doctype).change();
	// 	}
	// 	frappe.route_options = null;
	// },
	make: function() {
		var me = this;
		frappe.boot.user.can_import = frappe.boot.user.can_import.sort();

		$(frappe.render_template("data_transfer_wizard", this)).appendTo(this.page.main);
		this.select = this.page.main.find("select.doctype");
		this.doctype_column = this.page.main.find('.doctype-column');
		console.log(this.select);
		this.select.on("change", function() {
			me.doctype = $(this).val();
			frappe.model.with_doctype(me.doctype, function() {
				me.page.main.find(".export-tool-section").toggleClass(!!me.doctype);
				if(me.doctype) {
					// render select columns
					var parent_doctype = frappe.get_doc('DocType', me.doctype);
					parent_doctype["reqd"] = true;
					var doctype_list = [parent_doctype];
					
					frappe.meta.get_table_fields(me.doctype).forEach(function(df) {
						var d = frappe.get_doc('DocType', df.options);
						d["reqd"]=df.reqd;
						doctype_list.push(d);						
					});
					$(frappe.render_template("data_transfer_wizard_column", {doctype_list: doctype_list}))
						.appendTo(me.doctype_column.empty());
				}
			});
		});
		this.page.main.find('.btn-select-all').on('click', function() {
			me.doctype_column.find('.select-column-check').prop('checked', true);
		});
		this.page.main.find('.btn-select-all').on('click', function() {
			me.doctype_column.find('.select-column-check').prop('checked', true);
		});

		this.page.main.find('.btn-unselect-all').on('click', function() {
			me.doctype_column.find('.select-column-check').prop('checked', false);
		});

		this.page.main.find('.btn-select-mandatory').on('click', function() {
			me.doctype_column.find('.select-column-check').prop('checked', false);
			me.doctype_column.find('.select-column-check[data-reqd="1"]').prop('checked', true);
		});

		// this.page.main.find(".btn-download-template").on('click', function() {
		// 	window.open(me.get_export_url(false));
		// });

		// this.page.main.find(".btn-download-data").on('click', function() {
		// 	window.open(me.get_export_url(true));
		// });
	},
	show_import: function() {
		this.page.main.find('.import-tool-section').removeClass("hide");
		this.page.main.find('.export-tool-section').addClass("hide");
	},
	show_export: function() {
		this.page.main.find('.export-tool-section').removeClass("hide");
		this.page.main.find('.import-tool-section').addClass("hide");
	}
});


frappe.pages['data-transfer-wizard'].on_page_load = function(wrapper) {
	frappe.data_transfer_wizard = new frappe.DataTransferWizard(wrapper);
}


frappe.pages['data-transfer-wizard'].on_page_show = function(wrapper) {
	frappe.data_transfer_wizard; //&& frappe.data_transfer_wizard.set_route_options();
}