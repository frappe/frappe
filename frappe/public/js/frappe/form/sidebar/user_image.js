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

	const can_add = !image && frappe.ui.form.can_add_user_image(frm);
	image_section.find(".sidebar-image-edit").toggleClass("hide", !image);

	const preview = image_section
		.find(".sidebar-image-preview")
		.toggleClass("can-add", can_add)
		.toggleClass("can-view", Boolean(image));
	if (image || can_add) {
		preview.attr({
			tabindex: 0,
			role: "button",
			"aria-label": image ? __("View image") : __("Add image"),
		});
	} else {
		preview.removeAttr("tabindex role aria-label");
	}
	const tooltip = preview.data("es-tooltip");
	if (can_add && !tooltip) {
		frappe.ui.tooltip(preview, { text: __("Add image") });
	} else if (!can_add && tooltip) {
		tooltip.destroy();
		preview.removeData("es-tooltip");
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

frappe.ui.form.can_change_user_image = function (frm) {
	return Boolean(
		frm.meta.image_field &&
			!frm.fields_dict[frm.meta.image_field].df.read_only &&
			frm.get_perm(0, "write")
	);
};

// a new record has nowhere to attach the file until it is saved
frappe.ui.form.can_add_user_image = function (frm) {
	return frappe.ui.form.can_change_user_image(frm) && !frm.is_new();
};

frappe.ui.form.setup_user_image_event = function (frm) {
	// re-draw image on change of user image
	if (frm.meta.image_field) {
		frappe.ui.form.on(frm.doctype, frm.meta.image_field, function (frm) {
			frappe.ui.form.set_user_image(frm);
		});
	}

	if (!frm.meta.image_field) return;

	const can_write = frappe.ui.form.can_change_user_image(frm);
	const upload_image = function () {
		var field = frm.get_field(frm.meta.image_field);
		if (!field.$input) {
			field.make_input();
		}
		field.$input.trigger("attach_doc_image");
		frm.toolbar.close_sidebar?.();
	};
	const remove_image = () => frm.get_field(frm.meta.image_field).clear_attachment();

	frm.sidebar.image_wrapper
		.find(".sidebar-image-preview")
		.on("click", function () {
			if (frm.doc[frm.meta.image_field]) {
				frm.toolbar.close_sidebar?.();
				frappe.ui.form.show_user_image(frm, { can_write, upload_image, remove_image });
			} else if (frappe.ui.form.can_add_user_image(frm)) {
				upload_image();
			}
		})
		.on("keydown", function (e) {
			if ((e.key === "Enter" || e.key === " ") && this.hasAttribute("role")) {
				e.preventDefault();
				this.click();
			}
		});

	if (!can_write) return;

	const edit_button = frm.sidebar.image_wrapper.find(".sidebar-image-edit");
	// the phone sidebar closes on any button click, which would leave the menu behind
	edit_button.on("click", (e) => e.stopPropagation());

	new frappe.ui.Dropdown({
		trigger: edit_button,
		options: [
			{ label: __("Change image"), icon: "image-plus", onclick: upload_image },
			{
				label: __("Remove image"),
				icon: "trash-2",
				theme: "red",
				onclick: remove_image,
			},
		],
	});
};

frappe.ui.form.show_user_image = function (frm, { can_write, upload_image, remove_image }) {
	// show what the sidebar shows, since a form script may swap it (ERPNext Workstation)
	const image =
		frm.sidebar.image_section.find(".sidebar-image").attr("src") ||
		frm.doc[frm.meta.image_field];
	const title = frm.get_title();
	const dialog = new frappe.ui.Dialog({ size: "large" });
	dialog.$wrapper.addClass("sidebar-image-viewer");
	dialog.$body.append(
		$("<img>", { class: "sidebar-image-viewer-image", src: image, alt: title })
	);

	const download = function () {
		const link = document.createElement("a");
		link.href = image;
		link.download = image.split("/").pop().split("?")[0];
		// another site's image can't be downloaded, so it opens in a new tab instead
		link.target = "_blank";
		link.rel = "noopener";
		link.click();
	};
	const then_close = (action) => () => {
		dialog.$wrapper.one("hidden.bs.modal", action);
		dialog.hide();
	};
	const actions = [
		frappe.ui.button({
			icon: "download",
			variant: "ghost",
			tooltip: __("Download"),
			onclick: download,
		}),
	];
	if (can_write) {
		actions.push(
			frappe.ui.button({
				label: __("Change"),
				variant: "ghost",
				onclick: then_close(upload_image),
			}),
			frappe.ui.button({
				label: __("Remove"),
				variant: "ghost",
				onclick: then_close(remove_image),
			})
		);
	}

	dialog.custom_actions.append(
		$("<span>", { class: "sidebar-image-viewer-title", text: title, title })
	);
	dialog.standard_actions.prepend(actions);
	dialog.footer.removeClass("hide");
	dialog.$wrapper.on("hidden.bs.modal", () => dialog.$wrapper.remove());
	dialog.show();
	return dialog;
};
