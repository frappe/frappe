frappe.provide("frappe.search");

function search_documents(txt) {
	return [
		frappe.search.utils.get_creatables(txt),
		frappe.search.utils.get_search_in_list(txt),
		frappe.search.utils.get_doctypes(txt),
		frappe.search.utils.get_reports(txt),
		frappe.search.utils.get_pages(txt),
		frappe.search.utils.get_workspaces(txt),
		frappe.search.utils.get_dashboards(txt),
		frappe.search.utils.get_recent_pages(txt || ""),
		frappe.search.utils.get_executables(txt),
	].flat();
}

// interface for awesomebar_providers providers: (txt) => [results];
const default_providers = {
	search_default_documents(txt) {
		if (txt.charAt(0) === "#") {
			return frappe.tags.utils.get_tags(txt);
		} else {
			return search_documents(txt);
		}
	},

	get_type_wise_results(txt) {
		// search results have type "Report", "List", "Dashboard" etc which if
		// typed by user are not actually part of search string. So explicitly
		// add it back in results.

		if (!txt) return;

		let last_space = txt.lastIndexOf(" ");
		if (last_space === -1) return;

		let start_text = txt.slice(0, last_space);
		let end_txt = txt.slice(last_space + 1);

		let results = search_documents(start_text);

		return results.filter((r) => r.type?.toLowerCase().indexOf(end_txt.toLowerCase()) === 0);
	},

	add_help: (txt) => {
		const table_row = (col1, col2) =>
			`<tr><td style="width: 50%">${col1}</td><td>${col2}</td></tr>`;

		return [
			{
				value: __("Help on Search"),
				index: -10,
				default: "Help",
				onclick: function() {
					let txt = [
						'<table class="table table-bordered">',
						table_row(__("Create a new record"), __("new type of document")),
						table_row(__("List a document type"), __("document type..., e.g. customer")),
						table_row(__("Search in a document type"), __("text in document type")),
						table_row(__("Tags"), __("tag name..., e.g. #tag")),
						table_row(__("Open a module or tool"), __("module name...")),
						table_row(__("Calculate"), __("e.g. (55 + 434) / 4 or =Math.sin(Math.PI/2)...")),
						"</table>",
					].join("");
					frappe.msgprint(txt, __("Search Help"));
				},
			},
		];
	},

	get_random_password: (txt) => {
		if (txt && txt.toLowerCase().includes("random")) {
			return [
				{
					label: __("Generate Random Password"),
					index: -10,
					onclick: function() {
						frappe.msgprint(frappe.utils.get_random(16), __("Result"));
					},
				},
			];
		}
	},

	recent_pages: (txt) => {
		if (!txt) {
			return frappe.search.utils.get_recent_pages();
		}
	},

	frequently_visited_pages: (txt) => {
		if (!txt) {
			return frappe.search.utils.get_frequent_links();
		}
	},

	global_search: (txt) => {
		if (!txt) return;

		if (txt.charAt(0) === "#") {
			return;
		}
		return [
			{
				label: `
				<span class="flex justify-between text-medium">
					<span class="ellipsis">${__("Search for {0}", [frappe.utils.xss_sanitise(txt).bold()])}</span>
					<kbd>↵</kbd>
				</span>
			`,
				value: __("Search for {0}", [txt]),
				match: txt,
				index: 100,
				default: "Search",
				onclick: () => {
					frappe.searchdialog.search.init_search(txt, "global_search");
				},
			},
		];
	},

	search_in_current: (txt) => {
		if (!txt) return;

		var route = frappe.get_route();
		if (route[0] === "List" && txt.indexOf(" in") === -1) {
			// search in title field
			var meta = frappe.get_meta(frappe.container.page.list_view.doctype);
			var search_field = meta.title_field || "name";
			var options = {};
			options[search_field] = ["like", "%" + txt + "%"];
			return [
				{
					label: __("Find {0} in {1}", [txt.bold(), __(route[1]).bold()]),
					value: __("Find {0} in {1}", [txt, __(route[1])]),
					route_options: options,
					onclick: function() {
						cur_list.show();
					},
					index: 90,
					default: "Current",
					match: txt,
				},
			];
		}
	},

	calculator: (txt) => {
		if (!txt) return;

		var first = txt.substr(0, 1);
		if (first == parseInt(first) || first === "(" || first === "=") {
			if (first === "=") {
				txt = txt.substr(1);
			}
			try {
				var val = eval(txt);
				var formatted_value = __("{0} = {1}", [txt, (val + "").bold()]);
				return [
					{
						label: formatted_value,
						value: __("{0} = {1}", [txt, val]),
						match: val,
						index: 80,
						default: "Calculator",
						onclick: function() {
							frappe.msgprint(formatted_value, __("Result"));
						},
					},
				];
			} catch (e) {
				// pass
			}
		}
	},
};

frappe.search.awesomebar_providers.push(...Object.values(default_providers));
