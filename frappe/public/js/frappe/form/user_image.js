frappe.ui.form.set_user_image = function(frm) {

	var image_section = frm.sidebar.image_section;
	var image_field = frm.meta.image_field;
	var image = frm.doc[image_field];


	image_section.toggleClass('hide', image_field ? false : true);

	if(!image_field) {
		return;
	}

	// if image field has value
	if (image) {
		image_section
			.find(".sidebar-image")
			.css("background-image", 'url("' + image + '")')
			.removeClass("hide");

		image_section
			.find('.sidebar-standard-image')
			.addClass('hide');

	} else {
		image_section
			.find(".sidebar-image")
			.css("background-image", null)
			.addClass("hide");

		var title = frm.get_title();

		image_section
			.find('.sidebar-standard-image')
			.removeClass('hide')
			.find('.standard-image')
			.css({'background-color': frappe.get_palette(title)})
			.html(frappe.get_abbr(title));
	}

	frm.sidebar.image_wrapper.on('click', function() {
		var field = frm.get_field(frm.meta.image_field);
		if(!field.$input) {
			field.make_input();
		}
		field.$input.trigger('click');
	})

}