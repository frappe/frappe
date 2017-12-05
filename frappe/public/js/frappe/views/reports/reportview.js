// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.views.ReportFactory = frappe.views.Factory.extend({
	make: function(route) {
		new frappe.views.ReportViewPage(route[1], route[2]);
	}
});

frappe.views.ReportViewPage = Class.extend({
	init: function(doctype, docname) {
		if(!frappe.model.can_get_report(doctype)) {
			frappe.show_not_permitted(frappe.get_route_str());
			return;
		}

		this.doctype = doctype;
		this.docname = docname;
		this.page_name = frappe.get_route_str();
		this.make_page();

		var me = this;
		frappe.model.with_doctype(this.doctype, function() {
			me.make_report_view();
			if(me.docname) {
				frappe.model.with_doc('Report', me.docname, function(r) {
					me.parent.reportview.set_columns_and_filters(
						JSON.parse(frappe.get_doc("Report", me.docname).json || '{}'));
					me.parent.reportview.set_route_filters();
					me.parent.reportview.run();
				});
			} else {
				me.parent.reportview.set_route_filters();
				me.parent.reportview.run();
			}
		});
	},
	make_page: function() {
		var me = this;
		this.parent = frappe.container.add_page(this.page_name);
		frappe.ui.make_app_page({parent:this.parent, single_column:true});
		this.page = this.parent.page;

		frappe.container.change_to(this.page_name);

		$(this.parent).on('show', function(){
			if(me.parent.reportview.set_route_filters()) {
				me.parent.reportview.run();
			}
		});
	},
	make_report_view: function() {
		this.page.set_title(__(this.doctype));
		var module = locals.DocType[this.doctype].module;
		frappe.breadcrumbs.add(module, this.doctype);

		this.parent.reportview = new frappe.views.ReportView2({
			doctype: this.doctype,
			docname: this.docname,
			parent: this.parent
		});
	}
});
