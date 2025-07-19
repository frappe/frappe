frappe.ui.form.on("File", {
	refresh: function (frm) {
		// View File button
		if (frm.doc.file_url && frm.doc.file_url.startsWith("s3://")) {
			frm.add_custom_button(__("View File"), async () => {
				const url = await getRealFileUrl(frm.doc);
				if (url) {
					window.open(url);
				} else {
					frappe.msgprint(__("Không thể tạo link xem file"));
				}
			});
		} else if (frm.doc.file_url) {
			frm.add_custom_button(__("View File"), () => {
				const url = frappe.utils.is_url(frm.doc.file_url)
					? frm.doc.file_url
					: window.location.origin + frm.doc.file_url;
				window.open(url);
			});
		}

		// Download button
		if (!frm.doc.is_folder) {
			frm.add_custom_button(__("Download"), () => frm.trigger("download"), "fa fa-download");
		}

		// Public file warning
		if (!frm.doc.is_private) {
			frm.dashboard.set_headline(
				__("This file is public. It can be accessed without authentication."),
				"orange"
			);
		}

		frm.toggle_display("preview", false);
		frm.trigger("preview_file");

		let is_raster_image = /\.(gif|jpg|jpeg|tiff|png)$/i.test(frm.doc.file_url);
		let is_optimizable = !frm.doc.is_folder && is_raster_image && frm.doc.file_size > 0;

		// Optimize image
		is_optimizable && frm.add_custom_button(__("Optimize"), () => frm.trigger("optimize"));

		// Unzip if zip
		if (frm.doc.file_name && frm.doc.file_name.split(".").splice(-1)[0] === "zip") {
			frm.add_custom_button(__("Unzip"), () => frm.trigger("unzip"));
		}
	},

	preview_file: async function (frm) {
		let file_url = await getRealFileUrl(frm.doc);
		let file_extension = (frm.doc.file_type || "").toLowerCase();
		let $preview = "";

		if (frappe.utils.is_image_file(file_url)) {
			$preview = $(`<div class="img_preview">
				<img class="img-responsive" src="${frappe.utils.escape_html(file_url)}" />
			</div>`);
		} else if (frappe.utils.is_video_file(file_url)) {
			$preview = $(`<div class="img_preview">
				<video width="480" height="320" controls>
					<source src="${frappe.utils.escape_html(file_url)}">
					${__("Your browser does not support the video element.")}
				</video>
			</div>`);
		} else if (file_extension === "pdf") {
			$preview = $(`<div class="img_preview">
				<object style="background:#323639;" width="100%">
					<embed style="background:#323639;" width="100%" height="1190"
						src="${frappe.utils.escape_html(file_url)}" type="application/pdf">
				</object>
			</div>`);
		} else if (file_extension === "mp3") {
			$preview = $(`<div class="img_preview">
				<audio width="480" height="60" controls>
					<source src="${frappe.utils.escape_html(file_url)}" type="audio/mpeg">
					${__("Your browser does not support the audio element.")}
				</audio>
			</div>`);
		}

		if ($preview) {
			frm.toggle_display("preview", true);
			frm.get_field("preview_html").$wrapper.html($preview);
		}
	},

	download: function (frm) {
		let file_url = frm.doc.file_url;
		if (frm.doc.file_name) {
			file_url = file_url.replace(/#/g, "%23");
		}
		window.open(file_url);
	},

	optimize: function (frm) {
		frappe.show_alert(__("Optimizing image..."));
		frm.call("optimize_file").then(() => {
			frappe.show_alert(__("Image optimized"));
		});
	},

	unzip: function (frm) {
		frappe.call({
			method: "frappe.core.api.file.unzip_file",
			args: {
				name: frm.doc.name,
			},
			callback: function () {
				frappe.set_route("List", "File");
			},
		});
	},
});


async function getRealFileUrl(file_doc) {
	if (file_doc.file_url.startsWith("s3://")) {
		// Lấy presigned URL từ backend - pass S3 URL instead of doc name
		const res = await frappe.call({
			method: "frappe.utils.s3_file_handler.get_temp_s3_link",
			args: {
				file_name: file_doc.file_url,
				expiration: 600,
			},
		});
		console.log("S3 URL:", res);
		return res.message || "";
	} else if (!frappe.utils.is_url(file_doc.file_url)) {
		return window.location.origin + file_doc.file_url;
	} else {
		return file_doc.file_url;
	}
}