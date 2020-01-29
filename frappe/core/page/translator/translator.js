frappe.pages['translator'].on_page_load = function(wrapper) {
	frappe.TranslatorPortal = new TranslatorPortal(wrapper);
};

class TranslatorPortal {
	constructor(parent) {
		this.page = frappe.ui.make_app_page({
			parent: parent,
			title: 'Translation Portal',
			single_column: true
		});

		this.make();
	}
	make() {

		frappe.xcall('frappe.translate.get_messages').then(data => {
			const translated_messages = [];
			const untranslated_messages= [];
			data.forEach(element => {
				if (frappe._messages[element[1]]) {
					translated_messages.push(element);
				} else {
					untranslated_messages.push(element);
				}
			});
			$(frappe.render_template('translator', {
				'untranslated_messages': untranslated_messages,
				'translated_messages': translated_messages
			})).appendTo(this.page.body);
		});
	}
}