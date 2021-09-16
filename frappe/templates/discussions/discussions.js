frappe.ready(() => {

	setup_socket_io();

	add_color_to_avatars();

	expand_first_discussion();

	$(".search-field").keyup((e) => {
		search_topic(e);
	});

	$(".reply").click((e) => {
		show_new_topic_modal(e);
	});

	$("#login-from-discussion").click((e) => {
		login_from_discussion(e);
	});

	$(".sidebar-topic").click((e) => {
		if ($(e.currentTarget).attr("aria-expanded") == "true") {
			e.stopPropagation();
		}
	});

	$(document).on("keydown", ".comment-field", (e) => {
		if ((e.ctrlKey || e.metaKey) && (e.keyCode == 13 || e.which == 13) && !$(".discussion-modal").hasClass("show")) {
			e.preventDefault();
			submit_discussion(e);
		}
	});

	$(document).on("input", ".discussion-on-page .comment-field", (e) => {
		if ($(e.currentTarget).val()) {
			$(e.currentTarget).css("height", "48px");
			$(".cancel-comment").removeClass("hide").addClass("show");
			$(e.currentTarget).css("height", $(e.currentTarget).prop("scrollHeight"));
		} else {
			$(".cancel-comment").removeClass("show").addClass("hide");
			$(e.currentTarget).css("height", "48px");
		}
	});

	$(document).on("click", ".submit-discussion", (e) => {
		submit_discussion(e);
	});

	$(document).on("click", ".cancel-comment", () => {
		clear_comment_box();
	});

	if ($(document).width() <= 550) {
		$(document).on("click", ".sidebar-parent", () => {
			hide_sidebar();
		});
	}

	$(document).on("click", ".back", (e) => {
		back_to_sidebar(e);
	});

});

var show_new_topic_modal = (e) => {
	e.preventDefault();
	$("#discussion-modal").modal("show");
	var topic = $(e.currentTarget).attr("data-topic");
	$("#submit-discussion").attr("data-topic", topic ? topic : "");
};

var setup_socket_io = () => {
	const assets = [
		"/assets/frappe/js/lib/socket.io.min.js",
		"/assets/frappe/js/frappe/socketio_client.js"
	];

	frappe.require(assets, () => {
		if (window.dev_server) {
			frappe.boot.socketio_port = "9000";
		}
		frappe.socketio.init(9000);
		frappe.socketio.socket.on("publish_message", (data) => {
			publish_message(data);
		});
	});
};

var publish_message = (data) => {

	if ($(`.discussion-on-page[data-topic=${data.topic_info.name}]`).length) {
		post_message_cleanup();
		$(data.template).insertBefore(`.discussion-on-page[data-topic=${data.topic_info.name}] .discussion-form`);
	} else if ((decodeURIComponent($(".discussions-parent .discussions-card").attr("data-doctype")) == data.topic_info.reference_doctype
		&& decodeURIComponent($(".discussions-parent .discussions-card").attr("data-docname")) == data.topic_info.reference_docname)) {

		post_message_cleanup();
		data.new_topic_template = style_avatar_frame(data.new_topic_template);

		$(data.sidebar).insertAfter(`.discussions-sidebar .form-group`);
		$(`#discussion-group`).prepend(data.new_topic_template);

		if (data.topic_info.owner == frappe.session.user) {
			$(".discussion-on-page").collapse();
			$(".sidebar-topic").first().click();
		}
	} else if (data.topic_info.owner == frappe.session.user) {
		post_message_cleanup();
		window.location.reload();
	}

	update_reply_count(data.topic_info.name);
};

var post_message_cleanup = () => {
	$(".comment-field").val("");
	$(".comment-field").css("height", "48px");
	$("#discussion-modal").modal("hide");
	$("#no-discussions").addClass("hide");
	$(".cancel-comment").addClass("hide");
};

var update_reply_count = (topic) => {
	var reply_count = $(`[data-target='#t${topic}']`).find(".reply-count").text();
	reply_count = parseInt(reply_count) + 1;
	$(`[data-target='#t${topic}']`).find(".reply-count").text(reply_count);
};

var expand_first_discussion = () => {
	if ($(document).width() > 550) {
		$($(".discussions-parent .collapse")[0]).addClass("show");
		$($(".discussions-sidebar [data-toggle='collapse']")[0]).attr("aria-expanded", true);
	} else {
		$("#discussion-group").addClass("hide");
	}
};

var search_topic = (e) => {
	var input = $(e.currentTarget).val();

	var topics = $(".discussions-parent .discussion-topic-title");
	if (input.length < 3 || input.trim() == "") {
		topics.closest(".sidebar-parent").removeClass("hide");
		return;
	}

	topics.each((i, elem) => {
		var topic_id = $(elem).parent().attr("data-target");

		/* Check match in replies */
		var match_in_reply = false;
		var replies = $(`${topic_id}`);
		for (var reply of replies.find(".reply-text")) {
			if (has_common_substring($(reply).text(), input)) {
				match_in_reply = true;
				break;
			}
		}

		/* Match found in title or replies, then show */
		if (has_common_substring($(elem).text(), input) || match_in_reply) {
			$(elem).closest(".sidebar-parent").removeClass("hide");
		} else {
			$(elem).closest(".sidebar-parent").addClass("hide");
		}
	});
};

var has_common_substring = (str1, str2) => {
	var str1_arr = str1.toLowerCase().split(" ");
	var str2_arr = str2.toLowerCase().split(" ");

	var substring_found = false;
	for (var first_word of str1_arr) {
		for (var second_word of str2_arr) {
			if (first_word.indexOf(second_word) > -1) {
				substring_found = true;
				break;
			}
		}
	}
	return substring_found;
};

var submit_discussion = (e) => {
	e.preventDefault();
	e.stopImmediatePropagation();

	var title = $(".topic-title:visible").length ? $(".topic-title:visible").val().trim() : "";
	var reply = $(".comment-field:visible").val().trim();

	if (reply) {
		var doctype = $(e.currentTarget).attr("data-doctype");
		doctype = doctype ? decodeURIComponent(doctype) : doctype;

		var docname = $(e.currentTarget).attr("data-docname");
		docname = docname ? decodeURIComponent(docname) : docname;

		frappe.call({
			method: "frappe.website.doctype.discussion_topic.discussion_topic.submit_discussion",
			args: {
				"doctype": doctype ? doctype : "",
				"docname": docname ? docname : "",
				"reply": reply,
				"title": title,
				"topic_name": $(e.currentTarget).closest(".discussion-on-page").attr("data-topic")
			}
		})
	}
};

var login_from_discussion = (e) => {
	e.preventDefault();
	var redirect = $(e.currentTarget).attr("data-redirect") || window.location.href;
	window.location.href = `/login?redirect-to=${redirect}`;
};

var add_color_to_avatars = () => {
	var avatars = $(".avatar-frame");
	avatars.each((i, avatar) => {
		if (!$(avatar).attr("style")) {
			$(avatar).css(get_color_from_palette($(avatar)));
		}
	});
};

var get_color_from_palette = (element) => {
	var palette = frappe.get_palette(element.attr("title"));
	return {"background-color": `var(${palette[0]})`, "color": `var(${palette[1]})` }
};

var style_avatar_frame = (template) => {
	var $template = $(template);
	$template.find(".avatar-frame").css(get_color_from_palette($template.find(".avatar-frame")));
	return $template.prop("outerHTML");
};

var clear_comment_box = () => {
	if ($(".discussion-modal").hasClass("show")) {
		$("#discussion-modal").modal("hide");
	} else {
		$(".discussion-on-page .comment-field").val("");
	}
};

var hide_sidebar = () => {
	$(".discussions-sidebar").addClass("hide");
	$("#discussion-group").removeClass("hide");
};

var back_to_sidebar = () => {
	$(".discussions-sidebar").removeClass("hide");
	$("#discussion-group").addClass("hide");
	$(".discussion-on-page").collapse("hide");
};
