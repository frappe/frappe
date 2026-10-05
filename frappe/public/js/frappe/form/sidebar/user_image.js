frappe.ui.form.set_user_image = function (frm) {
	var image_section = frm.sidebar.image_section;
	var image_field = frm.meta.image_field;
	var image = frm.doc[image_field];
	var title_image = frm.page.$title_area.find(".title-image");

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
	} else {
		image_section.find(".sidebar-image").attr("src", null).addClass("hide");

		var title = frm.get_title();

		image_section
			.find(".sidebar-standard-image")
			.removeClass("hide")
			.find(".standard-image")
			.html(frappe.get_abbr(title));

		title_image.css("background-image", "").html(frappe.get_abbr(title));
	}
};

frappe.ui.form.setup_user_image_event = function (frm) {
	// re-draw image on change of user image
	if (frm.meta.image_field) {
		frappe.ui.form.on(frm.doctype, frm.meta.image_field, function (frm) {
			frappe.ui.form.set_user_image(frm);
		});
	}

	if (
		frm.meta.image_field &&
		!frm.fields_dict[frm.meta.image_field].df.read_only &&
		frm.perm[0].write
	) {
		var upload_image = function () {
			var field = frm.get_field(frm.meta.image_field);
			if (!field.$input) {
				field.make_input();
			}
			field.$input.trigger("attach_doc_image");
			frm.page.close_sidebar?.();
		};

		frm.sidebar.image_wrapper
			.attr({ tabindex: 0, role: "button", "aria-label": __("Change photo") })
			.on("keydown", function (e) {
				if (e.key === "Enter" || e.key === " ") {
					e.preventDefault();
					this.click();
				}
			});

		// without an image, upload directly instead of opening the menu below
		frm.sidebar.image_wrapper.on("click", function (e) {
			if (!frm.doc[frm.meta.image_field]) {
				e.stopImmediatePropagation();
				upload_image();
			}
		});

		new frappe.ui.Dropdown({
			trigger: frm.sidebar.image_wrapper,
			options: [
				{ label: __("Upload a photo"), icon: "image-plus", onclick: upload_image },
				{
					label: __("Remove photo"),
					icon: "trash",
					theme: "red",
					onclick: () => frm.get_field(frm.meta.image_field).clear_attachment(),
				},
			],
		});
	}
};
