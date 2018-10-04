// Copyright (c) 2016, Frappe Technologies and contributors
// For license information, please see license.txt

var address_fields = ["pincode","city", "county", "state"];

frappe.ui.form.on("Address", {
	refresh: function(frm) {
		
		frm.filters_set_using = "state";
		
		if(frm.doc.__islocal) {
			const last_doc = frappe.contacts.get_last_doc(frm);
			if(frappe.dynamic_link && frappe.dynamic_link.doc
					&& frappe.dynamic_link.doc.name == last_doc.docname) {
				frm.set_value('links', '');
				frm.add_child('links', {
					link_doctype: frappe.dynamic_link.doctype,
					link_name: frappe.dynamic_link.doc[frappe.dynamic_link.fieldname]
				});
			}
		}
		frm.set_query('link_doctype', "links", function() {
			return {
				query: "frappe.contacts.address_and_contact.filter_dynamic_link_doctypes",
				filters: {
					fieldtype: "HTML",
					fieldname: "address_html",
				}
			}
		});
		frm.refresh_field("links");

		// add filters to link fields
		address_fields.forEach(area_type => {
			if (frm.fields_dict[area_type].df.fieldtype == "Link"){
				frm.set_query(area_type, function() {
					return {
						"filters": {
							"administrative_area_type": area_type,
						}
					};
				});
			}
		});
	},
	validate: function(frm) {
		// clear linked customer / supplier / sales partner on saving...
		if(frm.doc.links) {
			frm.doc.links.forEach(function(d) {
				frappe.model.remove_from_locals(d.link_doctype, d.link_name);
			});
		}
	},
	after_save: function(frm) {
		frappe.run_serially([
			() => frappe.timeout(1),
			() => {
				const last_doc = frappe.contacts.get_last_doc(frm);
				if(frappe.dynamic_link && frappe.dynamic_link.doc
					&& frappe.dynamic_link.doc.name == last_doc.docname){
					frappe.set_route('Form', last_doc.doctype, last_doc.docname);
				}
			}
		]);
	}
});


/*
On click each field modify filters for other fields
for eg. on changing county first and state later state will not be able to affect filters
of other fields but revrese is not true
*/

function modify_administrative_area_filters(frm, all_address_fields, current_address_field, current_lft, current_rgt){
	all_address_fields.forEach(field_type => {
		if (field_type == current_address_field){
			//do nothing
		} else if (all_address_fields.indexOf(current_address_field) < address_fields.indexOf(field_type)) {
			frm.set_query(field_type, function() {
				return {
					"filters": [
						['Administrative Area','administrative_area_type',"=", field_type],
						['Administrative Area','rgt',">",current_rgt],
						['Administrative Area','lft',"<",current_lft],
					]
				};
			});
		} else {
			frm.set_query(field_type, function() {
				return {
					"filters": [
						['Administrative Area','administrative_area_type',"=", field_type],
						['Administrative Area','lft',">",current_lft],
						['Administrative Area','lft',"<",current_rgt],
					]
				};
			});
		}
	});
}

address_fields.forEach(type => {
	frappe.ui.form.on('Address', type, function(frm){
		var previous_filter_set_by = frm.filters_set_using;
		if (address_fields.indexOf(previous_filter_set_by) >= address_fields.indexOf(type)){
			if (frm.doc[type]){
				frm.filters_set_using = type;
				frappe.call({
					method: "frappe.contacts.doctype.address.address.get_administrative_area_details",
					args: {"administrative_area": frm.doc[type]},
					callback: function(data){
						if (data.message.status == 1){
							modify_administrative_area_filters(frm, address_fields, type, data.message.lft, data.message.rgt)
						}
					}
				});
			}
		}
	});
});