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
		this.edited_translations = {};
		this.setup_search_box();
		this.setup_language_filter();
		this.page.set_primary_action(__('Contribute Translations'), this.create_translations.bind(this));
		this.page.set_secondary_action(__('Refresh'), this.fetch_messages_then_render.bind(this));
		this.update_header();
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

		language_selector.set_value(frappe.boot.lang);
	}

	setup_search_box() {
		let search_box = this.page.add_field({
			fieldname: "search",
			fieldtype: "Data",
			label: __("Search Source Text"),
			change: () => {
				this.search_text = search_box.get_value();
				this.fetch_messages_then_render();
			}
		});
	}

	fetch_messages_then_render() {
		this.fetch_messages().then(messages => {
			this.messages = messages;
			this.render_messages(messages);
		});
	}

	fetch_messages() {
		frappe.dom.freeze(__('Fetching...'));
		return frappe
			.call("frappe.translate.get_messages", {
				language: this.language,
				search_text: this.search_text
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
					<span class="indicator ${this.get_indicator_color(message)}">
						<span>${frappe.utils.escape_html(message.source_text)}</span>
					</span>
				</div>
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
						fieldtype: "HTML",
						fieldname: "header",
						read_only: 1
					},
					{
						fieldtype: "Data",
						fieldname: "id",
						hidden: 1
					},
					{
						label: "Source Text",
						fieldtype: "Code",
						fieldname: "source_text",
						read_only: 1,
						enable_copy_button: 1
					},
					{
						fieldtype: "HTML",
						fieldname: "positions",
					},
					{
						label: "Context",
						fieldtype: "Code",
						fieldname: "context",
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
						fieldname: "translated_text",
						change: () => {
							let add_translation_btn = this.form.get_field("add_translation_btn");
							add_translation_btn.$input.attr('disabled', this.form.get_value('translated_text') === '');
						}
					},
					{
						label: __("Contribute Translation"),
						fieldtype: "Button",
						fieldname: "add_translation_btn",
						click: (values) => {
							values = this.form.get_values();
							this.edited_translations[values.id] = values;
							this.update_header();
						}
					}
				],
				body: this.wrapper.find(".translation-edit-form")
			});
			this.form.make();
			this.setup_header();
			let add_translation_btn = this.form.get_field("add_translation_btn");
			add_translation_btn.$wrapper.removeClass("input-max-width").addClass("text-right");
		}
		this.form.set_values(translation);
		this.form.set_df_property("doctype", "hidden", !translation.doctype);
		this.form.set_df_property("context", "hidden", !translation.context);
		this.set_status(translation);
		this.setup_additional_info(translation.id);
	}

	setup_additional_info(source_id) {
		frappe.xcall('frappe.translate.get_source_additional_info', {
			'source': source_id,
			'language': this.page.fields_dict['language'].get_value()
		}).then(data => {
			this.setup_positions(data.positions);
			// this.setup_contributions(data.contributions);
		});
	}

	setup_header() {
		this.form.get_field('header').$wrapper.html(`<div>
			<span class="translation-status"></span>
			<span class="pull-right">
				<a class="text-muted no-decoration">
					<i class="fa fa-chevron-left prev-item"></i>
				</a>
				<a class="text-muted no-decoration">
					<i class="fa fa-chevron-right next-item"></i>
				</a>
			</span>
		</div>`);
		this.setup_navigation_control();
	}

	set_status(translation) {
		this.form.get_field('header').$wrapper.find('.translation-status').html(`
			<span class="indicator ${this.get_indicator_color(translation)} text-muted">
				${this.get_indicator_status_text(translation)}
			</span>
		`);
	}

	setup_navigation_control() {
		const prev_item_btn = this.form.get_field('header').$wrapper.find('.prev-item');
		const next_item_btn = this.form.get_field('header').$wrapper.find('.next-item');
		prev_item_btn.click(() => {
			this.wrapper.find(".translation-item.active").prev().trigger('click');
		});
		next_item_btn.click(() => {
			this.wrapper.find(".translation-item.active").next().trigger('click');
		});
	}

	setup_positions(positions) {
		let position_dom = ``;
		if (positions && positions.length) {
			position_dom += `
				<div class="control-label">Positions</div>
			`;

			positions.forEach(position => {
				if (position.path.startsWith('DocType: ')) {
					position_dom += `<div>
						<span class="text-muted">${position.path}</span>
					</div>`;
				} else {
					position_dom += `<div>
						<a class="text-muted" target="_blank" href="${this.get_code_url(position.path, position.line_no, position.app)}">${position.path}</a>
					</div>`;
				}
			});
		}
		this.form.get_field('positions').$wrapper.html(position_dom);
	}

	setup_contributions(contributions) {
		let contributions_dom = ``;
		if (contributions && contributions.length) {
			contributions_dom += `
				<h4>Other Contributions</h4>
			`;

			contributions.forEach(contribution => {
				contributions_dom += `<div>
					<span class="pull-right text-muted">${frappe.datetime.comment_when(contribution.creation)}</span>
					<div class="text-muted">By ${contribution.contributor_name} </div>
					<span> ${contribution.translated} </span>
				</div>`;
			});
		}
		this.wrapper.find(".other-contributions").html(contributions_dom);
	}

	create_translations() {
		// frappe.dom.freeze(__('Submitting...'));
		frappe.xcall('frappe.core.doctype.translation.translation.create_translations', {
			translation_map: this.edited_translations,
			language: this.language
		}).then(() => {
			frappe.dom.unfreeze();
			frappe.show_alert(__('Successfully Submitted!'));
			this.edited_translations = {};
			this.update_header();
			this.fetch_messages_then_render();
		}).catch(() => frappe.dom.unfreeze()).finally(() => frappe.dom.unfreeze());
	}

	update_header() {
		let edited_translations_count = Object.keys(this.edited_translations).length;
		if (edited_translations_count) {
			this.page.set_indicator(__('{0} translations pending', [edited_translations_count]), 'orange');
		} else {
			this.page.set_indicator('');
		}
		this.page.btn_primary.prop('disabled', !edited_translations_count);
	}

	get_indicator_color(message_obj) {
		return !message_obj.translated ? 'red' : message_obj.translated_by_google ? 'orange' : 'blue';
	}

	get_indicator_status_text(message_obj) {
		return !message_obj.translated ? __('Untranslated') : message_obj.translated_by_google ? __('Google Translation') : __('Community Contribution');
	}

	get_code_url(path, line_no, app) {
		const code_path = path.substring(`apps/${app}`.length);
		return `https://github.com/frappe/${app}/blob/develop/${code_path}#L${line_no}`;
	}

}
