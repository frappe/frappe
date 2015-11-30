frappe.ui.form.on("Error Snapshot", "load", function(frm){
    frm.set_read_only(true);
});

frappe.ui.form.on("Error Snapshot", "refresh", function(frm){
    frm.set_df_property("view", "options", frappe.render_template("error_snapshot", {"doc": frm.doc}));
});
