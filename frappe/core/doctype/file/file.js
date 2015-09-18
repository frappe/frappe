frappe.ui.form.on("File", "refresh", function(frm) {
	if(!frm.doc.is_folder) {
		frm.add_custom_button(__('Download'), function() {
			window.open(frm.doc.file_url);
		}, "icon-download");
	}

	var wrapper = frm.get_field("preview_html").$wrapper;
	var is_viewable = frappe.utils.is_image_file(frm.doc.file_url);

	frm.toggle_display("preview", is_viewable);
	frm.toggle_display("preview_html", is_viewable);

	if(is_viewable){
		wrapper.html('<div class="img_preview">\
			<img class="img-responsive" src="'+frm.doc.file_url+'"></img>\
			</div>');
	} else {
		wrapper.empty();
	}
});
