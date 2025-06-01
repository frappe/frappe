// Copyright (c) 2015, nts Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

nts.provide("nts.help");

nts.help.youtube_id = {};

nts.help.has_help = function (doctype) {
	return nts.help.youtube_id[doctype];
};

nts.help.show = function (doctype) {
	if (nts.help.youtube_id[doctype]) {
		nts.help.show_video(nts.help.youtube_id[doctype]);
	}
};

nts.help.show_video = function (youtube_id, title) {
	if (nts.utils.is_url(youtube_id)) {
		const expression =
			'(?:youtube.com/(?:[^/]+/.+/|(?:v|e(?:mbed)?)/|.*[?&]v=)|youtu.be/)([^"&?\\s]{11})';
		youtube_id = youtube_id.match(expression)[1];
	}

	// (nts.help_feedback_link || "")
	let dialog = new nts.ui.Dialog({
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
	nts.utils.load_video_player().then(() => {
		plyr = new nts.Plyr(video[0], {
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
	doctype && nts.help.show(doctype);
});
