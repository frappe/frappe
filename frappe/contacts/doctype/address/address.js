// Copyright (c) 2016, Frappe Technologies and contributors
// For license information, please see license.txt

var address_fields = ["pincode","city", "county", "state"];

frappe.ui.form.on("Address", {
    refresh: function(frm) {

        frm.filters_set_using = "state";
        if(frm.doc.__islocal) {
            var last_route = frappe.route_history.slice(-2, -1)[0];
            let docname = last_route[2];
            if (last_route.length > 3)
                docname = last_route.slice(2).join("/");
            if(frappe.dynamic_link && frappe.dynamic_link.doc
                    && frappe.dynamic_link.doc.name==docname) {
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
    after_save: function() {
        frappe.run_serially([
            () => frappe.timeout(1),
            () => {
                var last_route = frappe.route_history.slice(-2, -1)[0];
                if(frappe.dynamic_link && frappe.dynamic_link.doc
                    && frappe.dynamic_link.doc.name == last_route[2]){
                    frappe.set_route(last_route[0], last_route[1], last_route[2]);
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
address_fields.forEach(type => {
    frappe.ui.form.on('Address', type, function(frm,cdt,cnt){
        var previous_filter_set_by = frm.filters_set_using;
        if (address_fields.indexOf(previous_filter_set_by) >= address_fields.indexOf(type)){
            if (frm.doc[type]){
                frm.filters_set_using = type
                frappe.call({
                    method: "frappe.contacts.doctype.address.address.get_administrative_area_details",
                    args: {"administrative_area": frm.doc[type]},
                    callback: function(data){
                        if (data.message.status == 1){
                            address_fields.forEach(address_type => {
                                if (address_type == type){
                                    //do nothing
                                }
                                else if (address_fields.indexOf(type) < address_fields.indexOf(address_type)) {
                                    frm.set_query(address_type, function() {
                                         return {
                                                 "filters": [
                                                    ['Administrative Area','administrative_area_type',"=",address_type],
                                                    ['Administrative Area','rgt',">",data.message.rgt],
                                                    ['Administrative Area','lft',"<",data.message.lft],
                                                 ]
                                         }
                                     });
                                }
                                else {
                                    frm.set_query(address_type, function() {
                                             return {
                                                     "filters": [
                                                      ['Administrative Area','administrative_area_type',"=",address_type],
                                                      ['Administrative Area','lft',">",data.message.lft],
                                                      ['Administrative Area','lft',"<",data.message.rgt],
                                                     ]
                                             }
                                     });
                                }
                            });
                        }
                    }
                });
            }
        }
    });
});
