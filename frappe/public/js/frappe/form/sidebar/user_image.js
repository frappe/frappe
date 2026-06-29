frappe.ui.form.set_user_image = function (frm) {
	var image_section = frm.sidebar.image_section;
	var image_field = frm.meta.image_field;
	var image = frm.doc[image_field];
	var title_image = frm.page.$title_area.find(".title-image");
	var image_actions = frm.sidebar.image_wrapper.find(".sidebar-image-actions");

	image_section.toggleClass("hide", image_field ? false : true);
	title_image.toggleClass("hide", image_field ? false : true);

	if (!image_field) {
		return;
	}

	// if image field has value
	if (image) {
		image_section.find(".sidebar-image").attr("src", image).removeClass("hide");
		image_section.find(".sidebar-standard-image").addClass("hide");
		title_image.css("background-image", `url("${image}")`).html("");
		image_actions.find(".sidebar-image-remove").show();
	} else {
		image_section.find(".sidebar-image").attr("src", null).addClass("hide");

		var title = frm.get_title();

		image_section
			.find(".sidebar-standard-image")
			.removeClass("hide")
			.find(".standard-image")
			.html(frappe.get_abbr(title));

		title_image.css("background-image", "").html(frappe.get_abbr(title));
		image_actions.find(".sidebar-image-remove").hide();
	}
};

frappe.ui.form.setup_user_image_event = function (frm) {
	// re-draw image on change of user image
	if (frm.meta.image_field) {
		frappe.ui.form.on(frm.doctype, frm.meta.image_field, function (frm) {
			frappe.ui.form.set_user_image(frm);
		});
	}

	if (frm.meta.image_field && !frm.fields_dict[frm.meta.image_field].df.read_only) {
		// clicking anywhere on the image wrapper triggers upload
		frm.sidebar.image_wrapper.on("click", function (e) {
			if ($(e.target).closest(".sidebar-image-remove").length) {
				return;
			}
			var field = frm.get_field(frm.meta.image_field);
			if (!field.$input) {
				field.make_input();
			}
			field.$input.trigger("attach_doc_image");
			frm.page.close_sidebar?.();
		});
	}

	// remove button
	frm.sidebar.image_wrapper.on("click", ".sidebar-image-remove", function (e) {
		e.stopPropagation();
		var field = frm.get_field(frm.meta.image_field);
		frm.attachments.remove_attachment_by_filename(frm.doc[frm.meta.image_field], function () {
			field.set_value("").then(() => frm.save());
		});
	});
};
