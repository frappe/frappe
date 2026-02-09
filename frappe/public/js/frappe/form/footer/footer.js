// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt
import FormTimeline from "./form_timeline";
frappe.ui.form.Footer = class FormFooter {
	constructor(opts) {
		$.extend(this, opts);
		this.make();
		this.make_comment_box();
		this.make_timeline();
		// render-complete
		$(this.frm.wrapper).on("render_complete", () => {
			this.refresh();
		});
	}
	make() {
		this.wrapper = $(frappe.render_template("form_footer", {})).appendTo(this.parent);
		this.wrapper.find(".btn-save").click(() => {
			this.frm.save("Save", null, this);
		});
		this.setup_scroll_to_top();
	}
	setup_scroll_to_top() {
		const $scroll_to_top_btn = this.wrapper.find(".scroll-to-top");
		const $scroll_container = $(".main-section");
		if (!$scroll_to_top_btn.length || !$scroll_container.length) return;
		const update = () =>
			this.toggle_scroll_to_top_button($scroll_to_top_btn, $scroll_container);
		const throttled_update = frappe.utils.throttle(update, 100);
		$scroll_container.off("scroll.form-footer").on("scroll.form-footer", throttled_update);
		$(window).off("resize.form-footer").on("resize.form-footer", throttled_update);
		setTimeout(update, 500);
	}
	toggle_scroll_to_top_button($button, $container) {
		if (!$button.length || !$container.length) return;
		const container_element = $container[0];
		if (!container_element) return;
		const scroll_top = $container.scrollTop();
		const scroll_height = container_element.scrollHeight || 0;
		const client_height = container_element.clientHeight || 0;
		const needs_scroll = scroll_height > client_height;
		const is_scrolled = scroll_top > 50;
		$button.toggleClass("show", needs_scroll && is_scrolled);
	}
	make_comment_box() {
		this.frm.comment_box = frappe.ui.form.make_control({
			parent: this.wrapper.find(".comment-box"),
			render_input: true,
			only_input: true,
			enable_mentions: true,
			df: {
				fieldtype: "Comment",
				fieldname: "comment",
			},
			on_submit: (comment) => {
				if (strip_html(comment).trim() != "" || comment.includes("img")) {
					this.frm.comment_box.disable();
					frappe
						.xcall("frappe.desk.form.utils.add_comment", {
							reference_doctype: this.frm.doctype,
							reference_name: this.frm.docname,
							content: comment,
							comment_email: frappe.session.user,
							comment_by: frappe.session.user_fullname,
						})
						.then(() => {
							this.frm.comment_box.set_value("");
							frappe.utils.play_sound("click");
						})
						.finally(() => {
							this.frm.comment_box.enable();
						});
				}
			},
		});
	}
	make_timeline() {
		this.frm.timeline = new FormTimeline({
			parent: this.wrapper.find(".timeline"),
			frm: this.frm,
		});
	}
	refresh() {
		if (this.frm.doc.__islocal) {
			this.parent.addClass("hide");
		} else {
			this.parent.removeClass("hide");
			this.frm.timeline.refresh();
		}
		this.refresh_comments_count();
	}

	refresh_comments_count() {
		let count = (this.frm.get_docinfo()?.comments || []).length;
		this.wrapper.find(".comment-count")?.html(count ? `(${count})` : "");
	}
};
