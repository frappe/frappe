frappe.ui.form.on("File", "refresh", function (frm) {
	if (!frm.doc.is_folder) {
		frm.add_custom_button(
			__("Download"),
			function () {
				var file_url = frm.doc.file_url;
				if (frm.doc.file_name) {
					file_url = file_url.replace(/#/g, "%23");
				}
				window.open(file_url);
			},
			"fa fa-download"
		);
	}

	frm.get_field("preview_html").$wrapper.html(`<div class="img_preview">
		<img class="img-responsive" src="${frm.doc.file_url}" onerror="cur_frm.toggle_display('preview', false)" />
	</div>`);

	var is_raster_image = /\.(gif|jpg|jpeg|tiff|png)$/i.test(frm.doc.file_url);
	var is_optimizable = !frm.doc.is_folder && is_raster_image && frm.doc.file_size > 0;

	if (is_optimizable) {
		frm.add_custom_button(__("Optimize"), function () {
			frappe.show_alert(__("Optimizing image..."));
			frm.call("optimize_file").then(() => {
				frappe.show_alert(__("Image optimized"));
			});
		});
	}

	if (frm.doc.file_name && frm.doc.file_name.split(".").splice(-1)[0] === "zip") {
		frm.add_custom_button(__("Unzip"), function () {
			frappe.call({
				method: "frappe.core.api.file.unzip_file",
				args: {
					name: frm.doc.name,
				},
				callback: function () {
					frappe.set_route("List", "File");
				},
			});
		});
	}
});
