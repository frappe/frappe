frappe.pages["translation-tool"].on_page_load = function(wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: "Translation Tool",
		single_column: true
	});

	new TranslationTool(page);
};

class TranslationTool {
	constructor(page) {
		this.page = page;
		this.wrapper = $(page.body);
		this.wrapper.append(frappe.render_template("translation_tool"));
		frappe.utils.bind_actions_with_object(this.wrapper, this);
		this.active_translation = null;
		this.setup_search_box();
		this.setup_language_filter();
	}

	setup_language_filter() {
		let languages = Object.keys(frappe.boot.lang_dict).map(language_label => {
			return {
				label: language_label,
				value: frappe.boot.lang_dict[language_label]
			};
		});

		let language_selector = this.page.add_field({
			fieldname: "language",
			fieldtype: "Select",
			options: languages,
			change: () => {
				let language = language_selector.get_value();
				this.language = language;
				this.fetch_messages_then_render();
			}
		});

		language_selector.set_value("hi"); // frappe.boot.lang
	}

	setup_search_box() {
		let search_box = this.page.add_field({
			fieldname: "search",
			fieldtype: "Data",
			label: __("Search Source Text"),
			change: () => {
				let search_text = search_box.get_value();
				this.fetch_messages_then_render(search_text);
			}
		});
	}

	fetch_messages_then_render(search_text) {
		this.fetch_messages(search_text).then(messages => {
			this.messages = messages;
			this.render_messages(messages);
		});
	}

	fetch_messages(search_text) {
		frappe.dom.freeze(__('Fetching...'));
		return frappe
			.call("frappe.translate.get_messages", {
				language: this.language,
				search_text: search_text
			})
			.then(r => {
				frappe.dom.unfreeze();
				return r.message;
			});
	}

	render_messages(messages) {
		let template = message => `
			<div
				class="translation-item"
				data-message-id="${encodeURIComponent(message.id)}"
				data-action="on_translation_click">
				<div class="bold ellipsis">
					<span>${message.source_text}</span>
				</div>
				<div class="text-muted">${message.path || message.doctype}</div>
			</div>
		`;

		let html = messages.map(template).join("");
		this.wrapper.find(".translation-item-container").html(html);
	}

	on_translation_click(e, $el) {
		let message_id = decodeURIComponent($el.data("message-id"));
		this.wrapper.find(".translation-item").removeClass("active");
		$el.addClass("active");
		this.active_translation = this.messages.find(m => m.id === message_id);
		this.edit_translation(this.active_translation);
	}

	edit_translation(translation) {
		if (!this.form) {
			this.form = new frappe.ui.FieldGroup({
				fields: [
					{
						label: "Source Text",
						fieldtype: "Code",
						fieldname: "source_text",
						read_only: 1
					},
					{
						label: "Path",
						fieldtype: "Code",
						fieldname: "path",
						read_only: 1
					},
					{
						label: "DocType",
						fieldtype: "Data",
						fieldname: "doctype",
						read_only: 1
					},
					{
						label: "Translated Text",
						fieldtype: "Code",
						fieldname: "translated_text"
					},
					{
						label: "Add Translation",
						fieldtype: "Button",
						fieldname: "add_translation_btn"
					}
				],
				body: this.wrapper.find(".translation-edit-form")
			});
			this.form.make();
			let add_translation_btn = this.form.get_field("add_translation_btn");
			add_translation_btn.$input.addClass("btn-primary btn-sm").removeClass("btn-xs");
		}
		this.form.set_values(translation);
		this.form.set_df_property("doctype", "hidden", !translation.doctype);
		this.form.set_df_property("path", "hidden", !translation.path);
	}
}
