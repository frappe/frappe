import Quill from "quill";
import Mention from "./quill-mention/quill.mention";

Quill.register("modules/mention", Mention, true);

frappe.ui.form.ControlComment = class ControlComment extends frappe.ui.form.ControlTextEditor {
	make_wrapper() {
		this.comment_wrapper = !this.no_wrapper
			? $(`
			<div class="comment-input-wrapper">
				<div class="comment-input-header">
				<span>${__("Comments")}</span>
				</div>
				<div class="comment-input-container">
				${frappe.avatar(frappe.session.user, "avatar-medium")}
					<div class="frappe-control col"></div>
				</div>
				<div class="checkbox hidden form-inline form-group" style="margin-left:48px;padding-top:5px;">
					<input type="checkbox" autocomplete="off" class="input-with-feedback" data-fieldtype="Check" data-fieldname="visible_to_mentioned_users">
					<span class="label-area">Visible to mentioned users</span>
				</div>
				<button class="btn hidden btn-comment btn-xs" style="margin-left:48px;">
					${__("Comment")}
				</button>
			</div>
		`)
			: $('<div class="frappe-control"></div>');

		this.comment_wrapper.appendTo(this.parent);

		// wrapper should point to frappe-control
		this.$wrapper = !this.no_wrapper
			? this.comment_wrapper.find(".frappe-control")
			: this.comment_wrapper;

		this.wrapper = this.$wrapper;

		this.button = this.comment_wrapper.find(".btn-comment");
		this.mention_wrapper = this.comment_wrapper.find(".checkbox");
		this.visible_to_mentioned_users = this.comment_wrapper.find('input[type="checkbox"]');
	}

	bind_events() {
		super.bind_events();

		this.button.click(() => {
			this.submit();
		});

		this.$wrapper.on("keydown", (e) => {
			const key = frappe.ui.keys.get_key(e);
			if (key === "ctrl+enter") {
				e.preventDefault();
				this.submit();
			}
		});

		this.quill.on(
			"text-change",
			frappe.utils.debounce(() => {
				this.update_state();
			}, 300)
		);
	}

	submit() {
		const mentioned_users = this.get_mentioned_users();

		const checked = this.visible_to_mentioned_users.prop("checked");
		this.on_submit && this.on_submit(this.get_value(), checked, mentioned_users);
	}
	get_mentioned_users() {
		const comment = $(this.get_value());
		const mention_wrapper = comment.find(".mention");
		let mentioned_user = [];
		if (mention_wrapper.length < 1) {
			return "";
		}
		mention_wrapper.each((index, element) => {
			mentioned_user.push($(element).data("id"));
		});
		return mentioned_user.join(",");
	}
	update_state() {
		const value = this.get_value();
		if (strip_html(value).trim() != "" || value.includes("img")) {
			this.button.removeClass("hidden").addClass("btn-primary");
			this.mention_wrapper.removeClass("hidden");
		} else {
			this.mention_wrapper.addClass("hidden");
			this.button.addClass("hidden").removeClass("btn-primary");
		}
	}

	get_quill_options() {
		const options = super.get_quill_options();
		return Object.assign(options, {
			theme: "bubble",
			bounds: this.quill_container[0],
			placeholder: __("Type a reply / comment"),
		});
	}

	get_toolbar_options() {
		return [
			["bold", "italic", "underline", "strike"],
			["blockquote", "code-block"],
			[{ direction: "rtl" }],
			["link", "image"],
			[{ list: "ordered" }, { list: "bullet" }],
			[{ align: [] }],
			["clean"],
		];
	}

	clear() {
		this.quill.setText("");
	}

	disable() {
		this.quill.disable();
		this.button.prop("disabled", true);
	}

	enable() {
		this.quill.enable();
		this.button.prop("disabled", false);
	}
};
