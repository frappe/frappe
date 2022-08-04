frappe.ready(() => {
	setup_socket_io();

	add_color_to_avatars();

	$(".search-field").keyup((e) => {
		search_topic(e);
	});

	$(".reply").click((e) => {
		show_new_topic_modal(e);
	});

	$(".login-from-discussion").click((e) => {
		login_from_discussion(e);
	});

	$(".sidebar-parent").click((e) => {
		if ($(e.currentTarget).attr("aria-expanded") == "true") {
			e.stopPropagation();
		}
	});

	$(document).on("keydown", ".comment-field", (e) => {
		if (
			(e.ctrlKey || e.metaKey) &&
			(e.keyCode == 13 || e.which == 13) &&
			!$(".discussion-modal").hasClass("show")
		) {
			e.preventDefault();
			submit_discussion(e);
		}
	});

	$(document).on("click", ".submit-discussion", (e) => {
		submit_discussion(e);
	});

	$(document).on("click", ".cancel-comment", () => {
		clear_comment_box();
	});

	$(document).on("click", ".sidebar-parent", () => {
		hide_sidebar();
	});

	$(document).on("click", ".back-button", (e) => {
		back_to_sidebar(e);
	});

	$(document).on("click", ".dismiss-reply", (e) => {
		dismiss_reply(e);
	});

	$(document).on("click", ".reply-card .dropdown-menu", (e) => {
		perform_action(e);
	});

	$(document).on("input", ".discussion-on-page .comment-field", (e) => {
		adjust_comment_box(e);
	});
});

const show_new_topic_modal = (e) => {
	e.preventDefault();
	$("#discussion-modal").modal("show");
	let topic = $(e.currentTarget).attr("data-topic");
	$("#submit-discussion").attr("data-topic", topic ? topic : "");
};

const setup_socket_io = () => {
	frappe.socketio.init(window.socketio_port || "9000");
	frappe.socketio.socket.on("publish_message", (data) => {
		publish_message(data);
	});
	frappe.socketio.socket.on("update_message", (data) => {
		update_message(data);
	});
	frappe.socketio.socket.on("delete_message", (data) => {
		delete_message(data);
	});
};

const publish_message = (data) => {
	const doctype = decodeURIComponent($(".discussions-parent").attr("data-doctype"));
	const docname = decodeURIComponent($(".discussions-parent").attr("data-docname"));
	const topic = data.topic_info;
	const single_thread = $(".is-single-thread").length;
	const first_topic = !$(".reply-card").length;
	const document_match_found =
		doctype == topic.reference_doctype && docname == topic.reference_docname;

	post_message_cleanup();
	data.template = hide_actions_on_conditions(data.template, data.reply_owner);
	data.template = style_avatar_frame(data.template);
	data.sidebar = style_avatar_frame(data.sidebar);
	data.new_topic_template = style_avatar_frame(data.new_topic_template);

	if ($(`.discussion-on-page[data-topic=${topic.name}]`).length) {
		$(data.template).insertBefore(
			`.discussion-on-page[data-topic=${topic.name}] .discussion-form`
		);
	} else if (!first_topic && !single_thread && document_match_found) {
		$(data.sidebar).insertBefore($(`.discussions-sidebar .sidebar-parent`).first());
		$(`#discussion-group`).prepend(data.new_topic_template);
		if (topic.owner == frappe.session.user) {
			$(".discussion-on-page") && $(".discussion-on-page").collapse();
			$(".sidebar-parent").first().click();
		}
	} else if (single_thread && document_match_found) {
		$(data.template).insertBefore(`.discussion-form`);
		$(".discussion-on-page").attr("data-topic", topic.name);
	} else if (topic.owner == frappe.session.user && document_match_found) {
		window.location.reload();
	}

	update_reply_count(topic.name);
};

const update_message = (data) => {
	const reply_card = $(`[data-reply=${data.reply_name}]`);
	reply_card.find(".reply-body").removeClass("hide");
	reply_card.find(".reply-edit-card").addClass("hide");
	reply_card.find(".reply-text").html(data.reply);
	reply_card.find(".reply-actions").addClass("hide");
};

const post_message_cleanup = () => {
	$(".topic-title").val("");
	$(".discussion-form .comment-field").val("");
	$("#discussion-modal").modal("hide");
	$("#no-discussions").addClass("hide");
	$(".cancel-comment").addClass("hide");
};

const update_reply_count = (topic) => {
	let reply_count = $(`[data-target='#t${topic}']`).find(".reply-count").text();
	reply_count = parseInt(reply_count) + 1;
	$(`[data-target='#t${topic}']`).find(".reply-count").text(reply_count);
};

const search_topic = (e) => {
	let input = $(e.currentTarget).val();

	let topics = $(".discussions-parent .discussion-topic-title");
	if (input.length < 3 || input.trim() == "") {
		topics.closest(".sidebar-parent").removeClass("hide");
		return;
	}

	topics.each((i, elem) => {
		let topic_id = $(elem).closest(".sidebar-parent").attr("data-target");

		/* Check match in replies */
		let match_in_reply = false;
		const replies = $(`${topic_id}`);
		for (const reply of replies.find(".reply-text")) {
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

const has_common_substring = (str1, str2) => {
	const str1_arr = str1.toLowerCase().split(" ");
	const str2_arr = str2.toLowerCase().split(" ");

	let substring_found = false;
	for (const first_word of str1_arr) {
		for (const second_word of str2_arr) {
			if (first_word.indexOf(second_word) > -1) {
				substring_found = true;
				break;
			}
		}
	}
	return substring_found;
};

const submit_discussion = (e) => {
	e.preventDefault();
	e.stopImmediatePropagation();

	const target = $(e.currentTarget);
	const reply_name = target.closest(".reply-card").data("reply");
	const title = $(".topic-title:visible").length ? $(".topic-title:visible").val().trim() : "";
	let reply = reply_name ? target.closest(".reply-card") : target.closest(".discussion-form");
	reply = reply.find(".comment-field").val().trim();

	if (reply) {
		let doctype = target.closest(".discussions-parent").attr("data-doctype");
		doctype = doctype ? decodeURIComponent(doctype) : doctype;

		let docname = target.closest(".discussions-parent").attr("data-docname");
		docname = docname ? decodeURIComponent(docname) : docname;

		frappe.call({
			method: "frappe.website.doctype.discussion_topic.discussion_topic.submit_discussion",
			args: {
				doctype: doctype ? doctype : "",
				docname: docname ? docname : "",
				reply: reply,
				title: title,
				topic_name: target.closest(".discussion-on-page").attr("data-topic"),
				reply_name: reply_name,
			},
		});
	}
};

const login_from_discussion = (e) => {
	e.preventDefault();
	const redirect = $(e.currentTarget).attr("data-redirect") || window.location.href;
	window.location.href = `/login?redirect-to=${redirect}`;
};

const add_color_to_avatars = () => {
	const avatars = $(".avatar-frame");
	avatars.each((i, avatar) => {
		if (!$(avatar).attr("style")) {
			$(avatar).css(get_color_from_palette($(avatar)));
		}
	});
};

const get_color_from_palette = (element) => {
	const palette = frappe.get_palette(element.attr("title"));
	return { "background-color": `var(${palette[0]})`, color: `var(${palette[1]})` };
};

const style_avatar_frame = (template) => {
	const $template = $(template);
	$template.find(".avatar-frame").length &&
		$template
			.find(".avatar-frame")
			.css(get_color_from_palette($template.find(".avatar-frame")));
	return $template.prop("outerHTML");
};

const clear_comment_box = () => {
	$(".discussion-form .comment-field").val("");
	$(".cancel-comment").removeClass("show").addClass("hide");
};

const hide_sidebar = () => {
	$(".discussions-sidebar").addClass("hide");
	$("#discussion-group").removeClass("hide");
	$(".search-field").addClass("hide");
	$(".reply").addClass("hide");
};

const back_to_sidebar = () => {
	$(".discussions-sidebar").removeClass("hide");
	$("#discussion-group").addClass("hide");
	$(".discussion-on-page").collapse("hide");
	$(".search-field").removeClass("hide");
	$(".reply").removeClass("hide");
};

const perform_action = (e) => {
	const action = $(e.target).data().action;
	const reply_card = $(e.target).closest(".reply-card");

	if (action === "edit") {
		reply_card.find(".reply-edit-card").removeClass("hide");
		reply_card.find(".reply-body").addClass("hide");
		reply_card.find(".reply-actions").removeClass("hide");
	} else if (action === "delete") {
		frappe.call({
			method: "frappe.website.doctype.discussion_reply.discussion_reply.delete_message",
			args: {
				reply_name: $(e.target).closest(".reply-card").data("reply"),
			},
		});
	}
};

const dismiss_reply = (e) => {
	const reply_card = $(e.currentTarget).closest(".reply-card");
	reply_card.find(".reply-edit-card").addClass("hide");
	reply_card.find(".reply-body").removeClass("hide");
	reply_card.find(".reply-actions").addClass("hide");
};

const adjust_comment_box = (e) => {
	if ($(e.currentTarget).val()) {
		$(".cancel-comment").removeClass("hide").addClass("show");
	} else {
		$(".cancel-comment").removeClass("show").addClass("hide");
	}
};

const hide_actions_on_conditions = (template, owner) => {
	let $template = $(template);
	frappe.session.user != owner && $template.find(".dropdown").addClass("hide");
	return $template.prop("outerHTML");
};

const delete_message = (data) => {
	$(`[data-reply=${data.reply_name}]`).addClass("hide");
};
