// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.provide('frappe.views.formview');

frappe.views.FormFactory = class FormFactory extends frappe.views.Factory {
	make(route) {
		var me = this,
			dt = route[1];

		if(!frappe.views.formview[dt]) {
			frappe.model.with_doctype(dt, function() {
				me.page = frappe.container.add_page("Form/" + dt);
				frappe.views.formview[dt] = me.page;
				me.page.frm = new frappe.ui.form.Form(dt, me.page, true);
				me.show_doc(route);
			});
		} else {
			me.show_doc(route);
		}

		if(!this.initialized) {
			$(document).on("page-change", function() {
				frappe.ui.form.close_grid_form();
			});

			frappe.realtime.on("new_communication", function(data) {
				frappe.timeline.new_communication(data);
			});

			frappe.realtime.on("delete_communication", function(data) {
				frappe.timeline.delete_communication(data);
			});

			frappe.realtime.on('update_communication', function(data) {
				frappe.timeline.update_communication(data);
			});

			frappe.realtime.on("doc_viewers", function(data) {
				frappe.ui.form.set_viewers(data);
			});
		}


		this.initialized = true;
	}

	show_doc(route) {
		var dt = route[1],
			dn = route.slice(2).join("/"),
			me = this;

		if(frappe.model.new_names[dn]) {
			dn = frappe.model.new_names[dn];
			frappe.set_route("Form", dt, dn);
			return;
		}

		frappe.model.with_doc(dt, dn, function(dn, r) {
			if(r && r['403']) return; // not permitted

			if(!(locals[dt] && locals[dt][dn])) {
				// doc not found, but starts with New,
				// make a new doc and set it
				var new_str = __("New") + " ";
				if(dn && dn.substr(0, new_str.length)==new_str) {
					var new_name = frappe.model.make_new_doc_and_get_name(dt, true);
					if(new_name===dn) {
						me.load(dt, dn);
					} else {
						frappe.set_route("Form", dt, new_name)
					}
				} else {
					frappe.show_not_found(route);
				}
				return;
			}
			me.load(dt, dn);
		});
	}

	load(dt, dn) {
		frappe.container.change_to("Form/" + dt);
		frappe.views.formview[dt].frm.refresh(dn);
		// console.log('this', this);
		this.setup_modal();
	}

	setup_modal() {
		$(document).on('keydown',null, 'ctrl+shift+m', (e)=> {
			// e.stopImmediatePropagation();
			if($(this.page).is(':hidden')) {
				console.log('yesss');
				return;	
			}
			console.log('this', this.page);
			console.log('modal');
			let fields = this.get_section_fields();
			let field_labels =  [];
			fields.forEach((f)=> {field_labels.push(f.label)});
			console.log('labels', field_labels);
			const d = new frappe.ui.Dialog({
				title: __('Go to Field'),
				fields: [
					{
						fieldtype: 'Select',
						fieldname: 'go_to_field',
						label: 'Select Field',
						options: field_labels,
						reqd: 1
					}
				]
			});
			d.set_primary_action("Go", () => {
				let field = d.get_values().go_to_field;
				console.log('field', field);
				let element = fields.find( f=> f.label == field).section_body;
				console.log('element', element);
				if(element.hasClass('hide')) {
					console.log('true');
					element.removeClass('hide');
				}
				frappe.utils.scroll_to(element);
				// this.group_by = this.meta.fields.find( f => f.label == d.get_values().group_by).fieldname;
				// this.aggregate_on = this.meta.fields.find( f => f.label == d.get_values().aggregate_on).fieldname;

				// let sql_aggregate_function = {
				// 	Count: "count",
				// 	Sum: "sum",
				// 	Average: "avg",
				// }
				// this.aggregate_function = sql_aggregate_function[d.get_values().aggregate_function];
				d.hide();
			});
			d.show();
		})
	}

	get_section_fields() {
		let fields = [];
		// this.page.frm.fields.forEach((f) => {
		// 	if(f.df.fieldtype!=='Section Break' && !f.df.hidden && f.disp_status!=='None' && f.df.label) {
		// 		fields.push(f.df.label);
		// 	}
		// });
		// console.log('fields', fields);
		// return fields;

		this.page.frm.layout.sections.forEach((section)=> {
			section.fields_list.forEach((f)=> {
				if(f.df.fieldtype!=='Section Break' && !f.df.hidden && f.disp_status!=='None' && f.df.label) {
					let field = {};
					field.label = f.df.label;
					field.section_body = section.body;
					field.section = section.df.label;
					fields.push(field);
				}
			})
		})
		console.log('fields', fields);
		return fields;
	}
}
