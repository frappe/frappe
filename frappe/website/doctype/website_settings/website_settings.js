frappe.ui.form.on('Website Settings', {
	refresh: function(frm) {
		frm.add_custom_button(__('View Website'), () => {
			window.open('/', '_blank');
		});
	},

	onload: function(frm) {
		var language_area = $('<div style="min-height: 300px">')
			.appendTo(frm.fields_dict.languages_html.wrapper);
		frm.language_editor = new frappe.LanguageEditor(frm, language_area);
		},

	set_banner_from_image: function(frm) {
		if (!frm.doc.banner_image) {
			frappe.msgprint(__("Select a Brand Image first."));
		}
		frm.set_value("brand_html", "<img src='"+ frm.doc.banner_image
			+"' style='max-width: 150px;'>");
	},

	onload_post_render: function(frm) {
		frm.trigger('set_parent_label_options');
	},

	set_parent_label_options: function(frm) {
		frappe.meta.get_docfield("Top Bar Item", "parent_label", frm.docname).options =
			frm.events.get_parent_options(frm, "top_bar_items");

		if ($(frm.fields_dict.top_bar_items.grid.wrapper).find(".grid-row-open")) {
			frm.fields_dict.top_bar_items.grid.refresh();
		}
	},

	set_parent_label_options_footer: function(frm) {
		frappe.meta.get_docfield("Top Bar Item", "parent_label", frm.docname).options =
			frm.events.get_parent_options(frm, "footer_items");

		if ($(frm.fields_dict.footer_items.grid.wrapper).find(".grid-row-open")) {
			frm.fields_dict.footer_items.grid.refresh();
		}
	},

	set_parent_options: function(frm, doctype, name) {
		var item = frappe.get_doc(doctype, name);
		if(item.parentfield === "top_bar_items") {
			frm.trigger('set_parent_label_options');
		}
		else if (item.parentfield === "footer_items") {
			frm.trigger('set_parent_label_options_footer');
		}
	},

	get_parent_options: function(frm, table_field) {
		var items = frm.doc[table_field] || [];
		var main_items = [''];
		for (var i in items) {
			var d = items[i];
			if(!d.parent_label && !d.url && d.label) {
				main_items.push(d.label);
			}
		}
		return main_items.join('\n');
	},
});

frappe.ui.form.on('Top Bar Item', {
	parent_label: function(frm, doctype, name) {
		frm.events.set_parent_options(frm, doctype, name);
	},

	url: function(frm, doctype, name) {
		frm.events.set_parent_options(frm, doctype, name);
	},

	label: function(frm, doctype, name) {
		frm.events.set_parent_options(frm, doctype, name);
	},
});

frappe.LanguageEditor = Class.extend({
	init: function(frm, wrapper) {
		this.wrapper = wrapper;
		this.frm = frm;
		this.make();
	},
	make: function() {
		var me = this;
		this.frm.doc.__onload.all_languages.forEach(function(l) {
			$(repl('<div class="col-sm-6"><div class="checkbox">\
				<label><input type="checkbox" class="language-check" data-language="%(language_code)s">\
				%(language_name)s</label></div></div>', {language_code: l.language_code, language_name: l.language_name})).appendTo(me.wrapper);
		});
		this.bind();
		this.refresh();
	},
	refresh: function() {
		var me = this;
		$.each((me.frm.doc.website_languages || []), function(i, d) {
			me.wrapper.find(".language-check[data-language='"+ d.language +"']").prop("checked", true);
		});
	},
	bind: function() {
		var me = this;
		this.wrapper.on("change", ".language-check", function() {
			var language = $(this).attr('data-language');
			if ($(this).prop("checked")) {
				me.frm.add_child("website_languages", {"language": language});
			}
			else {
				me.frm.doc.website_languages = $.map(me.frm.doc.website_languages || [], function(d) { 
					if(d.language != language){ return d } });
			}
		});
	}
})