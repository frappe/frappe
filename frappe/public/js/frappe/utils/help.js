// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.provide("frappe.help");

frappe.help.youtube_id = {};

frappe.help.has_help = function (doctype) {
	return frappe.help.youtube_id[doctype];
};

frappe.help.show = function (doctype) {
	if (frappe.help.youtube_id[doctype]) {
		frappe.help.show_video(frappe.help.youtube_id[doctype]);
	}
};

frappe.help.show_video = function (youtube_id, title) {
	if (frappe.utils.is_url(youtube_id)) {
		const expression =
			'(?:youtube.com/(?:[^/]+/.+/|(?:v|e(?:mbed)?)/|.*[?&]v=)|youtu.be/)([^"&?\\s]{11})';
		youtube_id = youtube_id.match(expression)[1];
	}

	// (frappe.help_feedback_link || "")
	let dialog = new frappe.ui.Dialog({
		title: title || __("Help"),
		size: "large",
	});

	let video = $(
		`<div class="video-player" data-plyr-provider="youtube" data-plyr-embed-id="${youtube_id}"></div>`
	);
	video.appendTo(dialog.body);

	dialog.show();
	dialog.$wrapper.addClass("video-modal");

	let plyr;
	frappe.utils.load_video_player().then(() => {
		plyr = new frappe.Plyr(video[0], {
			hideControls: true,
			resetOnEnd: true,
		});
	});

	dialog.onhide = () => {
		plyr?.destroy();
	};
};

$("body").on("click", "a.help-link", function () {
	var doctype = $(this).attr("data-doctype");
	doctype && frappe.help.show(doctype);
});
