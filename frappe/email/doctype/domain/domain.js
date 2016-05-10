frappe.ui.form.on("Domain", {
    email_id:function(frm){
        frm.set_value("domain_name",frm.doc.email_id.split("@")[1])
    },
    refresh:function(frm){
        if (frm.doc.__islocal != 1) {
            route = frappe.get_prev_route()
            if (frappe.route_titles["return to email_account"]){
                delete frappe.route_titles["return to email_account"];
                //frappe.route_titles["domain"] = cur_frm.doc.domain_name;
                frappe.set_route(route);
            }
        }
    }
})
