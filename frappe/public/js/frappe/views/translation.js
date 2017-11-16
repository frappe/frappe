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
		});
		return fields;
	},
	translate_action: function(args){
		var 
			self = this,
			translated = {
				'source': self.source_text, 
				'language': frappe.defaults.get_global_default('language')
			}, key, splitted;

		for (key in args){
			splitted = key.split("_");
			translated[splitted[splitted.length - 1]] = args[key];
		}
		frappe.call({
			'method': 'frappe.translate.update_record_translation',
			'args': {
				'translated': translated
			},
			'callback': function(res){
				if (!res.exc){
					cur_dialog.hide();
					frappe.msgprint('Translations added successfull!');
					cur_frm.reload_doc();
				}
			}
		});
	}
});
