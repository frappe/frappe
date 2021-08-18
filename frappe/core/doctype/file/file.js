frappe.ui.form.on("File", "refresh", function(frm) {
	if(!frm.doc.is_folder) {
		frm.add_custom_button(__('Download'), function() {
			var file_url = frm.doc.file_url;
			if (frm.doc.file_name) {
				file_url = file_url.replace(/#/g, '%23');
			}
			window.open(file_url);
		}, "fa fa-download");
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

	if(frm.doc.file_name && frm.doc.file_name.split('.').splice(-1)[0]==='zip') {
		frm.add_custom_button(__('Unzip'), function() {
			frappe.call({
				method: "frappe.core.doctype.file.file.unzip_file",
				args: {
					name: frm.doc.name,
				},
				callback: function() {
					frappe.set_route('List', 'File');
				}
			});
		});
	}
});
