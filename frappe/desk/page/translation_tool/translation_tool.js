frappe.pages['translation-tool'].on_page_load = function(wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __('Translation Tool'),
		single_column: true,
		card_layout: true,
	});

	frappe.translation_tool = new TranslationTool(page);
};

class TranslationTool {
	constructor(page) {
		this.page = page;
		this.wrapper = $(page.body);
		this.wrapper.append(frappe.render_template('translation_tool'));
		frappe.utils.bind_actions_with_object(this.wrapper, this);
		this.active_translation = null;
		this.edited_translations = {};
		this.setup_search_box();
		this.setup_language_filter();
		this.page.set_primary_action(
			__('Contribute Translations'),
			this.show_confirmation_dialog.bind(this)
		);
		this.page.set_secondary_action(
			__('Refresh'),
			this.fetch_messages_then_render.bind(this)
		);
		this.update_header();
	}

	setup_language_filter() {
		let languages = Object.keys(frappe.boot.lang_dict).map(language_label => {
			let value = frappe.boot.lang_dict[language_label];
			return {
				label: `${language_label} (${value})`,
				value: value
			};
		});

		let language_selector = this.page.add_field({
			fieldname: 'language',
			fieldtype: 'Select',
			options: languages,
			change: () => {
				let language = language_selector.get_value();
				localStorage.setItem('translation_language', language);
				this.language = language;
				this.fetch_messages_then_render();
			}
		});
		let translation_language = localStorage.getItem('translation_language');
		if (translation_language || frappe.boot.lang !== 'en') {
			language_selector.set_value(translation_language || frappe.boot.lang);
		} else {
			frappe.prompt(
				{
					label: __('Please select target language for translation'),
					fieldname: 'language',
					fieldtype: 'Select',
					options: languages,
					reqd: 1
				},
				values => {
					language_selector.set_value(values.language);
				},
				__('Select Language')
			);
		}
	}

	setup_search_box() {
		let search_box = this.page.add_field({
			fieldname: 'search',
			fieldtype: 'Data',
			label: __('Search Source Text'),
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
		this.setup_local_contributions();
	}

	fetch_messages() {
		frappe.dom.freeze(__('Fetching...'));
		return frappe
			.xcall('frappe.translate.get_messages', {
				language: this.language,
				search_text: this.search_text
			})
			.then(messages => {
				return messages;
			})
			.finally(() => {
				frappe.dom.unfreeze();
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

		let html = messages.map(template).join('');
		this.wrapper.find('.translation-item-container').html(html);
	}

	on_translation_click(e, $el) {
		let message_id = decodeURIComponent($el.data('message-id'));
		this.wrapper.find('.translation-item').removeClass('active');
		$el.addClass('active');
		this.active_translation = this.messages.find(m => m.id === message_id);
		this.edit_translation(this.active_translation);
	}

	edit_translation(translation) {
		if (this.form) {
			this.form.set_values({});
		}
		this.get_additional_info(translation.id).then(data => {
			this.make_edit_form(translation, data);
		});
	}

	get_additional_info(source_id) {
		frappe.dom.freeze('Fetching...');
		return frappe.xcall('frappe.translate.get_source_additional_info', {
			source: source_id,
			language: this.page.fields_dict['language'].get_value()
		}).finally(frappe.dom.unfreeze);
	}

	make_edit_form(translation, { contributions, positions }) {
		if (!this.form) {
			this.form = new frappe.ui.FieldGroup({
				fields: [
					{
						fieldtype: 'HTML',
						fieldname: 'header',
						read_only: 1
					},
					{
						fieldtype: 'Data',
						fieldname: 'id',
						hidden: 1
					},
					{
						label: 'Source Text',
						fieldtype: 'Code',
						fieldname: 'source_text',
						read_only: 1,
						enable_copy_button: 1
					},
					{
						label: 'Context',
						fieldtype: 'Code',
						fieldname: 'context',
						read_only: 1
					},
					{
						label: 'DocType',
						fieldtype: 'Data',
						fieldname: 'doctype',
						read_only: 1
					},
					{
						label: 'Translated Text',
						fieldtype: 'Small Text',
						fieldname: 'translated_text',
					},
					{
						label: 'Suggest',
						fieldtype: 'Button',
						click: () => {
							let { id, translated_text, source_text } = this.form.get_values();
							let existing_value = this.form.translation_dict.translated_text;
							if (
								is_null(translated_text) ||
								existing_value === translated_text
							) {
								delete this.edited_translations[id];
							} else if (existing_value !== translated_text) {
								this.edited_translations[id] = {
									id,
									translated_text,
									source_text
								};
							}
							this.update_header();
						}
					},
					{
						fieldtype: 'Section Break',
						fieldname: 'contributed_translations_section',
						label: 'Contributed Translations'
					},
					{
						fieldtype: 'HTML',
						fieldname: 'contributed_translations'
					},
					{
						fieldtype: 'Section Break',
						collapsible: 1,
						label: 'Occurences in source code'
					},
					{
						fieldtype: 'HTML',
						fieldname: 'positions'
					},
				],
				body: this.wrapper.find('.translation-edit-form')
			});

			this.form.make();
			this.setup_header();
		}

		this.form.set_values(translation);
		this.form.translation_dict = translation;
		this.form.set_df_property('doctype', 'hidden', !translation.doctype);
		this.form.set_df_property('context', 'hidden', !translation.context);
		this.set_status(translation);

		this.setup_contributions(contributions);
		this.setup_positions(positions);
	}

	setup_header() {
		this.form.get_field('header').$wrapper.html(`<div>
			<span class="translation-status"></span>
		</div>`);
	}

	set_status(translation) {
		this.form.get_field('header').$wrapper.find('.translation-status').html(`
			<span class="indicator-pill ${this.get_indicator_color(translation)}">
				${this.get_indicator_status_text(translation)}
			</span>
		`);
	}

	setup_positions(positions) {
		let position_dom = '';
		if (positions && positions.length) {
			position_dom = positions.map(position => {
				if (position.path.startsWith('DocType: ')) {
					return `<div>
						<span class="text-muted">${position.path}</span>
					</div>`;
				} else {
					return `<div>
						<a
							class="text-muted"
							target="_blank"
							href="${this.get_code_url(position.path, position.line_no, position.app)}">
							${position.path}
						</a>
					</div>`;
				}
			}).join('');
		}
		this.form.get_field('positions').$wrapper.html(position_dom);
	}

	setup_contributions(contributions) {
		const contributions_exists = contributions && contributions.length;
		if (contributions_exists) {
			let contributions_html = contributions.map(c => {
				return `
					<div class="contributed-translation flex justify-between align-center">
						<div class="ellipsis">${c.translated}</div>
						<div class="text-muted small">
							${comment_when(c.creation)}
						</div>
					</div>
				`;
			});
			this.form.get_field('contributed_translations').html(contributions_html);
		}
		this.form.set_df_property('contributed_translations_section', 'hidden', !contributions_exists);
	}
	show_confirmation_dialog() {
		this.confirmation_dialog = new frappe.ui.Dialog({
			fields: [
				{
					label: __('Language'),
					fieldname: 'language',
					fieldtype: 'Data',
					read_only: 1,
					bold: 1,
					default: this.language
				},
				{
					fieldtype: 'HTML',
					fieldname: 'edited_translations'
				}
			],
			title: __('Confirm Translations'),
			no_submit_on_enter: true,
			primary_action_label: __('Submit'),
			primary_action: values => {
				this.create_translations(values).then(this.confirmation_dialog.hide());
			}
		});
		this.confirmation_dialog.get_field('edited_translations').html(`
			<table class="table table-bordered">
				<tr>
					<th>${__('Source Text')}</th>
					<th>${__('Translated Text')}</th>
				</tr>
				${Object.values(this.edited_translations).map(t => `
					<tr>
						<td>${t.source_text}</td>
						<td>${t.translated_text}</td>
					</tr>
				`).join('')}
			</table>
		`);
		this.confirmation_dialog.show();
	}
	create_translations() {
		frappe.dom.freeze(__('Submitting...'));
		return frappe
			.xcall(
				'frappe.core.doctype.translation.translation.create_translations',
				{
					translation_map: this.edited_translations,
					language: this.language
				}
			)
			.then(() => {
				frappe.dom.unfreeze();
				frappe.show_alert({ message: __('Successfully Submitted!'), indicator: 'success'});
				this.edited_translations = {};
				this.update_header();
				this.fetch_messages_then_render();
			})
			.finally(() => frappe.dom.unfreeze());
	}

	setup_local_contributions() {
		// TODO: Refactor
		frappe
			.xcall('frappe.translate.get_contributions', {
				language: this.language
			})
			.then(messages => {
				let template = message => `
					<div
						class="translation-item"
						data-message-id="${encodeURIComponent(message.name)}"
						data-action="show_translation_status_modal">
						<div class="bold ellipsis">
							<span class="indicator ${this.get_contribution_indicator_color(message)}">
								<span>${frappe.utils.escape_html(message.source_text)}</span>
							</span>
						</div>
					</div>
				`;

				let html = messages.map(template).join('');
				this.wrapper.find('.translation-item-tr').html(html);
			});
	}

	show_translation_status_modal(e, $el) {
		let message_id = decodeURIComponent($el.data('message-id'));

		frappe.xcall('frappe.translate.get_contribution_status', { message_id })
			.then(doc => {
				let d = new frappe.ui.Dialog({
					title: __('Contribution Status'),
					fields: [
						{
							fieldname: 'source_message',
							label: __('Source Message'),
							fieldtype: 'Data',
							read_only: 1
						},
						{
							fieldname: 'translated',
							label: __('Translated Message'),
							fieldtype: 'Data',
							read_only: 1
						},
						{
							fieldname: 'contribution_status',
							label: __('Contribution Status'),
							fieldtype: 'Data',
							read_only: 1
						},
						{
							fieldname: 'modified_by',
							label: __('Verified By'),
							fieldtype: 'Data',
							read_only: 1,
							depends_on: doc => {
								return doc.contribution_status == 'Verified';
							}
						},
					]
				});
				d.set_values(doc);
				d.show();
			});
	}

	update_header() {
		let edited_translations_count = Object.keys(this.edited_translations)
			.length;
		if (edited_translations_count) {
			let message = '';
			if (edited_translations_count == 1) {
				message = __('{0} translation pending', [edited_translations_count]);
			} else {
				message = __('{0} translations pending', [edited_translations_count]);
			}
			this.page.set_indicator(message, 'orange');
		} else {
			this.page.set_indicator('');
		}
		this.page.btn_primary.prop('disabled', !edited_translations_count);
	}

	get_indicator_color(message_obj) {
		return !message_obj.translated ? 'red' : message_obj.translated_by_google ? 'orange' : 'blue';
	}

	get_indicator_status_text(message_obj) {
		if (!message_obj.translated) {
			return __('Untranslated');
		} else if (message_obj.translated_by_google) {
			return __('Google Translation');
		} else {
			return __('Community Contribution');
		}
	}

	get_contribution_indicator_color(message_obj) {
		return message_obj.contribution_status == 'Pending' ? 'orange' : 'green';
	}

	get_code_url(path, line_no, app) {
		const code_path = path.substring(`apps/${app}`.length);
		return `https://github.com/frappe/${app}/blob/develop/${code_path}#L${line_no}`;
	}
}
