// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.provide("frappe.help");

frappe.help.youtube_id = {};

frappe.help.has_help = function(doctype) {
	return frappe.help.youtube_id[doctype];
}

frappe.help.show = function(doctype) {
	if(frappe.help.youtube_id[doctype]) {
		frappe.help.show_video(frappe.help.youtube_id[doctype]);
	}
}

frappe.help.show_video = function(youtube_id, title) {
	if($("body").width() > 768) {
		var size = [670, 377];
	} else {
		var size = [560, 315];
	}
	var dialog = frappe.msgprint('<iframe width="'+size[0]+'" height="'+size[1]+'" \
		src="https://www.youtube.com/embed/'+ youtube_id +'" \
		frameborder="0" allowfullscreen></iframe>' + (frappe.help_feedback_link || ""),
	title || __("Help"));

	dialog.$wrapper.addClass("video-modal");
}

$("body").on("click", "a.help-link", function() {
	var doctype = $(this).attr("data-doctype");
	doctype && frappe.help.show(doctype);
});
