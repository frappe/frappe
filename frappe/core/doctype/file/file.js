frappe.ui.form.on("File", "onload", function(frm) {
    if(frappe.utils.is_image_file(frm.doc.file_url)){
        frm.doc.preview = '<div class="img_preview">\
                <img style="max-widht:130px;max-height:130px;" \
                    src="'+frm.doc.file_url+'"></img>\
                </div>';
        frm.refresh_field("preview");
    }
})

frappe.ui.form.on("File", "refresh", function(frm) {
    frm.add_custom_button(__('Download'), function(){
        window.open(frm.doc.file_url);
    }, "icon-download");
})

// frappe.ui.form.on("File", "download", function(frm) {
//     window.open(frm.doc.file_url);
// })
