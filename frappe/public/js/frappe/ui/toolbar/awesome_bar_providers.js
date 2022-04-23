frappe.provide('frappe.search');

// interface for awesomebar_providers providers: (txt) => [results];

const default_providers = {
	add_help: (txt) => {
		const table_row = (col1, col2) => `<tr><td style="width: 50%">${col1}</td><td>${col2}</td></tr>`;

		return [{
			value: __("Help on Search"),
			index: -10,
			default: "Help",
			onclick: function() {
				let txt = [
					'<table class="table table-bordered">',
					table_row(__('Create a new record'), __("new type of document")),
					table_row(__("List a document type"), __("document type..., e.g. customer")),
					table_row(__("Search in a document type"), __("text in document type")),
					table_row(__("Tags"), __("tag name..., e.g. #tag")),
					table_row(__("Open a module or tool"), __("module name...")),
					table_row(__("Calculate"), __("e.g. (55 + 434) / 4 or =Math.sin(Math.PI/2)...")),
					'</table>'
				].join('');
				frappe.msgprint(txt, __("Search Help"));
			}
		}]
	},
}


frappe.search.awesomebar_providers.push(...Object.values(default_providers))
