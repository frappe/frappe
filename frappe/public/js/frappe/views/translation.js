frappe.views.TranslationManager = Class.extend({
	init: function(opts){
		$.extend(this, opts);
		this.make();
	},
	make: function(){
		this.dialog = new frappe.ui.Dialog({
			'fields': this.prepare(),
			'title': [__('Translate'), this.fieldname],
			'no_submit_on_enter': true,
			'primary_action_label': __('Translate'),
			'primary_action': this.translate_action.bind(this)
		});
		this.dialog.show();
	},
	prepare: function(){
		var fields = [
			{'fieldname': 'source', 'fieldtype': 'HTML', 'options': 
				format('<code>{0}</code>', [this.source_text])
			}
		],
		me = this;
		frappe.boot.translate_languages.forEach(function(lang){
			if (frappe.defaults.get_global_default('lang') == lang) return;
			var translated = null;
			if (me.doc.__onload.translations
				&& me.doc.__onload.translations[me.source_text]
				&& me.doc.__onload.translations[me.source_text][lang] ){
				translated = me.doc.__onload.translations[me.source_text][lang].target_name;
			}
			fields.push({
				'label': lang,
				'fieldtype': 'Section Break',
				'collapsible': true
			});
			fields.push({
				'fieldname': ['trans', md5(self.source_text), lang].join('_'),
				'fieldtype': 'Text',
				'default': translated
			});
			fields.push({
				'label': __('Remove Translation'),
				'fieldname': ['delete', md5(self.source_text), lang].join('_'),
				'fieldtype': 'Check',
				'default': 0
			});
		});
		return fields;
	},
	translate_action: function(args){
		var 
			self = this,
			translated = {
				'source': self.source_text, 
				'language': frappe.defaults.get_global_default('language')
			}, key, splitted, for_removal = [];

		for (key in args){
			splitted = key.split("_");

			if (splitted[0] == 'delete' && args[key] === 1){
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
			'callback': function(res){
				if (!res.exc){
					// Wont work properly without an setTimeout
					setTimeout(function(){
						cur_dialog.hide();
						frappe.show_alert({message: __("Translations updated"), indicator:"green"})
						cur_frm.refresh();
					}, 500);
				}
			}
		});
	}
});
