/**
 * Created by jedi-paul on 7/1/19.
 */
frappe.ui.form.on("System Settings", "refresh", function(frm){
    frappe.call({
        method: "frappe.core.doctype.system_settings.system_settings.load",
        callback: function(data){
            frappe.all_timezones = data.message.timezones;
            frm.set_df_property("time_zone", "options", frappe.all_timezones);
            $.each(data.message.defaults, function (key, val) {
                frm.set_value(key, val);
                frappe.sys_defaults[key] = val;
            })
        }
    });
    if (frm.doc.enable_backup_encryption && !frm.doc.password_encryption) {
        frm.fields_dict.new_password_encryption.df.reqd = 1;
        frm.fields_dict.new_password_encryption.df.hidden = 0;
        frm.refresh_field("new_password_encryption");
        frm.fields_dict.confirm_password_encryption.df.reqd = 1;
        frm.fields_dict.confirm_password_encryption.df.hidden = 0;
        frm.refresh_field("confirm_password_encryption");
    }
    if (!frm.doc.change_encryption_password && frm.doc.password_encryption) {
        frm.fields_dict.new_password_encryption.df.reqd = 0;
        frm.fields_dict.new_password_encryption.df.hidden = 1;
        frm.refresh_field("new_password_encryption");
        frm.fields_dict.confirm_password_encryption.df.reqd = 0;
        frm.fields_dict.confirm_password_encryption.df.hidden = 1;
        frm.refresh_field("confirm_password_encryption");
    }
});
frappe.ui.form.on("System Settings", "enable_password_policy", function(frm){
    if (frm.doc.enable_password_policy == 0) {
        frm.set_value("minimum_password_score", "");
    } else {
        frm.set_value("minimum_password_score", "2");
    }
});
frappe.ui.form.on("System Settings", "enable_two_factor_auth", function(frm){
    if (frm.doc.enable_two_factor_auth == 0) {
        frm.set_value("bypass_2fa_for_retricted_ip_users", 0);
        frm.set_value("bypass_restrict_ip_check_if_2fa_enabled", 0);
    }
});
frappe.ui.form.on("System Settings", "enable_backup_encryption", function(frm){
    if ((frm.doc.enable_backup_encryption && frm.doc.new_password_encryption != frm.doc.confirm_password_encryption) || !frm.doc.confirm_password_encryption) {
        frm.fields_dict.new_password_encryption.df.reqd = 1;
        frm.fields_dict.new_password_encryption.df.hidden = 0;
        frm.refresh_field("new_password_encryption");
        frm.fields_dict.confirm_password_encryption.df.reqd = 1;
        frm.fields_dict.confirm_password_encryption.df.hidden = 0;
        frm.refresh_field("confirm_password_encryption");
    } else {
        frm.doc.new_password_encryption = "";
        frm.doc.confirm_password_encryption = "";
        frm.doc.password_encryption = "";
        frm.fields_dict.new_password_encryption.df.reqd = 0;
        frm.refresh_field("new_password_encryption");
        frm.fields_dict.confirm_password_encryption.df.reqd = 0;
        frm.refresh_field("confirm_password_encryption");
    }
});
frappe.ui.form.on("System Settings", "change_encryption_password", function(frm){
    if (frm.doc.enable_backup_encryption && frm.doc.change_encryption_password) {
        frm.fields_dict.new_password_encryption.df.reqd = 1;
        frm.fields_dict.new_password_encryption.df.hidden = 0;
        frm.refresh_field("new_password_encryption");
        frm.fields_dict.confirm_password_encryption.df.reqd = 1;
        frm.fields_dict.confirm_password_encryption.df.hidden = 0;
        frm.refresh_field("confirm_password_encryption");
    } else {
        frm.fields_dict.new_password_encryption.df.reqd = 0;
        frm.fields_dict.new_password_encryption.df.hidden = 1;
        frm.refresh_field("new_password_encryption");
        frm.fields_dict.confirm_password_encryption.df.reqd = 0;
        frm.fields_dict.confirm_password_encryption.df.hidden = 1;
        frm.refresh_field("confirm_password_encryption");
    }
});
frappe.ui.form.on("System Settings", "validate", function(frm){
    if (frm.doc.new_password_encryption != frm.doc.confirm_password_encryption && frm.doc.enable_backup_encryption) {
        frappe.msgprint("Password encrytion is not matched with the confirmed password.");
        frappe.validated = False;
    } else if (frm.doc.new_password_encryption == frm.doc.confirm_password_encryption && frm.doc.enable_backup_encryption) {
        if (frm.doc.confirm_password_encryption) {
            frm.doc.password_encryption = frm.doc.confirm_password_encryption;
            frm.fields_dict.new_password_encryption.df.reqd = 0;
            frm.fields_dict.confirm_password_encryption.df.reqd = 0;
            frm.doc.new_password_encryption = "";
            frm.doc.confirm_password_encryption = "";
            frappe.msgprint("Password is saved and cannot be retrieved/viewed.");
        }
    }
    if (frm.doc.change_encryption_password) {
        frm.doc.change_encryption_password = 0;
    }
});
frappe.ui.form.on("System Settings", "confirm_password_encryption", function(){
    if (frm.doc.new_password_encryption == frm.doc.confirm_password_encryption) {
        $('input[data-fieldname="confirm_password_encryption"]')[0].style = "border-color: #08c708";
    } else {
        $('input[data-fieldname="confirm_password_encryption"]')[0].style = "border-color: red";
    }
});
frappe.ui.form.on("System Settings", "confirm_password_encryption", function(frm){
    if (frm.doc.new_password_encryption == frm.doc.confirm_password_encryption) {
        $('input[data-fieldname="confirm_password_encryption"]')[0].style = "border-color: #08c708";
    } else {
        $('input[data-fieldname="confirm_password_encryption"]')[0].style = "border-color: red";
    }
});