
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
	
	make: function() {
		var me = this;
		frappe.boot.user.can_import = frappe.boot.user.can_import.sort();
		$(frappe.render_template("data_transfer_wizard", this)).appendTo(this.page.main);
		this.select = this.page.main.find("select.doctype");
		//this.doctype_column = this.page.main.find('.doctype-column');
		console.log(this.select);
		// this.select.on("change", function() {
		// 	me.doctype = $(this).val();
		// 	frappe.model.with_doctype(me.doctype, function() {
		// 		me.page.main.find(".export-tool-section").toggleClass(!!me.doctype);
		// 		if(me.doctype) {
		// 			// render select columns
		// 			var parent_doctype = frappe.get_doc('DocType', me.doctype);
		// 			parent_doctype["reqd"] = true;
		// 			var doctype_list = [parent_doctype];
					
		// 			frappe.meta.get_table_fields(me.doctype).forEach(function(df) {
		// 				var d = frappe.get_doc('DocType', df.options);
		// 				d["reqd"]=df.reqd;
		// 				doctype_list.push(d);						
		// 			});
		// 			$(frappe.render_template("data_transfer_wizard_column", {doctype_list: doctype_list}))
		// 				.appendTo(me.doctype_column.empty());
		// 		}
		// 	});
		// });
		
	}
});


frappe.pages['data-transfer-wizard'].on_page_load = function(wrapper) {
	frappe.data_transfer_wizard = new frappe.DataTransferWizard(wrapper);
}


frappe.pages['data-transfer-wizard'].on_page_show = function(wrapper) {
	frappe.data_transfer_wizard; //&& frappe.data_transfer_wizard.set_route_options();
}