frappe.views.TranslationManager = class TranslationManager {
	constructor(opts) {
		Object.assign(this, opts);
		this.make();
	}

	make() {
		this.dialog = new frappe.ui.Dialog({
			fields: this.get_fields(),
			title: __('Translate {0}', [this.df.label]),
			no_submit_on_enter: true,
			primary_action_label: __('Update Translations'),
			primary_action: this.update_translations.bind(this)
		});
		this.dialog.show();
	}

	get_fields() {
		const data = this.get_translations_data();

		var fields = [
			{
				label: __('Source Text'),
				fieldname: 'source',
				fieldtype: 'Data',
				read_only: 1,
				bold: 1,
				default: this.source_text
			},
			{
				label: __('Translations'),
				fieldname: 'translation_table',
				fieldtype: 'Table',
				fields: [
					{
						label: 'Language',
						fieldname: 'lang',
						fieldtype: 'Link',
						options: 'Language',
						in_list_view: 1,
						columns: 3
					},
					{
						label: 'Translation',
						fieldname: 'translation',
						fieldtype: 'Data',
						in_list_view: 1,
						columns: 7
					}
				],
				data: data,
				get_data() {
					return data;
				}
			}
		];

		// frappe.boot.translate_languages.forEach(function (lang) {
		// 	if (frappe.defaults.get_global_default('lang') == lang) return;
		// 	var translated = null;
		// 	if (me.doc.__onload.translations &&
		// 		me.doc.__onload.translations[me.source_text] &&
		// 		me.doc.__onload.translations[me.source_text][lang]) {
		// 		translated = me.doc.__onload.translations[me.source_text][lang].target_name;
		// 	}
		// 	fields.push({
		// 		'label': lang,
		// 		'fieldtype': 'Section Break',
		// 		'collapsible': true
		// 	});
		// 	fields.push({
		// 		'fieldname': ['trans', md5(self.source_text), lang].join('_'),
		// 		'fieldtype': 'Text',
		// 		'default': translated
		// 	});
		// 	fields.push({
		// 		'label': __('Remove Translation'),
		// 		'fieldname': ['delete', md5(self.source_text), lang].join('_'),
		// 		'fieldtype': 'Check',
		// 		'default': 0
		// 	});
		// });
		return fields;
	}

	get_translations_data() {
		let data = [];
		(frappe.boot.translate_languages || []).map(lang => {
			if (this.doc.__onload.translations &&
				this.doc.__onload.translations[this.source_text] &&
				this.doc.__onload.translations[this.source_text][lang]
			) {
				data.push({
					idx: data.length,
					lang: lang,
					translation: this.doc.__onload.translations[this.source_text][lang].target_name
				});
			}
		});

		return data;
	}

	update_translations({ source, translation_table }) {
		const translation_dict = {};
		translation_table.map(row => {
			translation_dict[row.lang] = row.translation;
		});

		frappe.call('frappe.translate.update_translations_for_source', {
			source,
			translation_dict
		}).then(r => {
			console.log(r);
		});
	}

	translate_action(args) {
		var
			self = this,
			translated = {
				'source': self.source_text,
				'language': frappe.defaults.get_global_default('language')
			},
			key, splitted, for_removal = [];

		for (key in args) {
			splitted = key.split("_");

			if (splitted[0] == 'delete' && args[key] === 1) {
				for_removal.push(splitted[2])
			} else if (splitted[0] != 'delete' && !for_removal.includes(splitted[2]) && args[key] && args[key.replace('trans', 'delete')] !== 1) {
				translated[splitted[2]] = args[key];
			}
		}

		frappe.call({
			'method': 'frappe.translate.update_record_translation',
			'args': {
				'translated': translated,
				'for_removal': for_removal
			},
			'callback': function (res) {
				if (!res.exc) {
					// Wont work properly without an setTimeout
					setTimeout(function () {
						cur_dialog.hide();
						frappe.show_alert({
							message: __("Translations updated"),
							indicator: "green"
						});
						cur_frm.refresh();
					}, 500);
				}
			}
		});
	}
};

