// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt
frappe.provide("frappe.search");
frappe.provide("frappe.tags");

frappe.search.AwesomeBar = class AwesomeBar {
	setup(element) {
		var me = this;

		$(".search-bar").removeClass("hidden");
		var $input = $(element);
		var input = $input.get(0);

		this.options = [];
		this.global_results = [];

		var awesomplete = new Awesomplete(input, {
			minChars: 0,
			maxItems: 99,
			autoFirst: true,
			list: [],
			filter: function (text, term) {
				return true;
			},
			data: function (item, input) {
				return {
					label: item.index || "",
					value: item.value,
				};
			},
			item: function (item, term) {
				const d = this.get_item(item.value);
				let target = "#";
				if (d.route) {
					target = frappe.router.make_url(
						frappe.router.convert_from_standard_route(
							frappe.router.get_route_from_arguments(
								typeof d.route === "string" ? [d.route] : d.route
							)
						)
					);
				}
				let html = `<span>${__(d.label || d.value)}</span>`;

				if (d.description && d.value !== d.description) {
					html +=
						'<br><span class="text-muted ellipsis">' + __(d.description) + "</span>";
				}

				return $("<li></li>")
					.data("item.autocomplete", d)
					.html(`<a style="font-weight:normal" href="${target}">${html}</a>`)
					.get(0);
			},
			sort: function (a, b) {
				return b.label - a.label;
			},
		});

		// Added to aid UI testing of global search
		input.awesomplete = awesomplete;

		this.awesomplete = awesomplete;

		$input.on(
			"input",
			frappe.utils.debounce(function (e) {
				var value = e.target.value;
				var txt = value.trim().replace(/\s\s+/g, " ");
				var last_space = txt.lastIndexOf(" ");
				me.global_results = [];

				me.options = [];

				if (txt && txt.length > 1) {
					if (last_space !== -1) {
						me.set_specifics(txt.slice(0, last_space), txt.slice(last_space + 1));
					}
					me.add_defaults(txt);
					me.options = me.options.concat(me.build_options(txt));
					me.options = me.options.concat(me.global_results);
				} else {
					me.options = me.options.concat(
						me.deduplicate(frappe.search.utils.get_recent_pages(txt || ""))
					);
					me.options = me.options.concat(frappe.search.utils.get_frequent_links());
				}
				me.add_help();

				awesomplete.list = me.deduplicate(me.options);
			}, 100)
		);

		var open_recent = function () {
			if (!this.autocomplete_open) {
				$(this).trigger("input");
			}
		};
		$input.on("focus", open_recent);

		$input.on("awesomplete-open", function (e) {
			me.autocomplete_open = e.target;
		});

		$input.on("awesomplete-close", function (e) {
			me.autocomplete_open = false;
		});

		$input.on("awesomplete-select", function (e) {
			var o = e.originalEvent;
			var value = o.text.value;
			var item = awesomplete.get_item(value);

			if (item.route_options) {
				frappe.route_options = item.route_options;
			}

			if (item.onclick) {
				item.onclick(item.match);
			} else {
				let event = o.originalEvent;
				if (event.ctrlKey || event.metaKey) {
					frappe.open_in_new_tab = true;
				}
				if (item.route[0].startsWith("https://")) {
					window.open(item.route[0], "_blank");
					return;
				}
				frappe.set_route(item.route);
			}
			$input.val("");
			$input.trigger("blur");
		});

		$input.on("awesomplete-selectcomplete", function (e) {
			$input.val("");
		});

		$input.on("keydown", (e) => {
			if (e.key == "Escape") {
				$input.trigger("blur");
			}
		});
		frappe.search.utils.setup_recent();
	}

	add_help() {
		this.options.push({
			value: __("Help on Search"),
			index: -10,
			default: "Help",
			onclick: function () {
				var txt =
					'<table class="table table-bordered">\
					<tr><td style="width: 50%">' +
					__("Create a new record") +
					"</td><td>" +
					__("new type of document") +
					"</td></tr>\
					<tr><td>" +
					__("List a document type") +
					"</td><td>" +
					__("document type..., e.g. customer") +
					"</td></tr>\
					<tr><td>" +
					__("Search in a document type") +
					"</td><td>" +
					__("text in document type") +
					"</td></tr>\
					<tr><td>" +
					__("Tags") +
					"</td><td>" +
					__("tag name..., e.g. #tag") +
					"</td></tr>\
					<tr><td>" +
					__("Open a module or tool") +
					"</td><td>" +
					__("module name...") +
					"</td></tr>\
					<tr><td>" +
					__("Calculate") +
					"</td><td>" +
					__("e.g. (55 + 434) / 4 or =Math.sin(Math.PI/2)...") +
					"</td></tr>\
				</table>";
				frappe.msgprint(txt, __("Search Help"));
			},
		});
	}

	set_specifics(txt, end_txt) {
		var me = this;
		var results = this.build_options(txt);
		results.forEach(function (r) {
			if (r.type && r.type.toLowerCase().indexOf(end_txt.toLowerCase()) === 0) {
				me.options.push(r);
			}
		});
	}

	add_defaults(txt) {
		this.make_global_search(txt);
		this.make_search_in_current(txt);
		this.make_calculator(txt);
		this.make_random(txt);
	}

	build_options(txt) {
		var options = frappe.search.utils
			.get_creatables(txt)
			.concat(
				frappe.search.utils.get_search_in_list(txt),
				frappe.search.utils.get_doctypes(txt),
				frappe.search.utils.get_reports(txt),
				frappe.search.utils.get_pages(txt),
				frappe.search.utils.get_workspaces(txt),
				frappe.search.utils.get_dashboards(txt),
				frappe.search.utils.get_recent_pages(txt || ""),
				frappe.search.utils.get_executables(txt),
				frappe.search.utils.get_marketplace_apps(txt)
			);
		if (txt.charAt(0) === "#") {
			options = frappe.tags.utils.get_tags(txt);
		}
		var out = this.deduplicate(options);
		return out.sort(function (a, b) {
			return b.index - a.index;
		});
	}

	deduplicate(options) {
		var out = [],
			routes = [];
		options.forEach(function (option) {
			if (option.route) {
				if (
					option.route[0] === "List" &&
					option.route[2] !== "Report" &&
					option.route[2] !== "Inbox"
				) {
					option.route.splice(2);
				}

				var str_route =
					typeof option.route === "string" ? option.route : option.route.join("/");
				if (routes.indexOf(str_route) === -1) {
					out.push(option);
					routes.push(str_route);
				} else {
					var old = routes.indexOf(str_route);
					if (out[old].index < option.index && !option.recent) {
						out[old] = option;
					}
				}
			} else {
				out.push(option);
				routes.push("");
			}
		});
		return out;
	}

	set_global_results(global_results, txt) {
		this.global_results = this.global_results.concat(global_results);
	}

	make_global_search(txt) {
		// let search_text = $(this.awesomplete.ul).find('.search-text');

		// if (txt.charAt(0) === "#" || !txt) {
		// 	search_text && search_text.remove();
		// 	return;
		// }

		// if (!search_text.length) {
		// 	search_text = $(this.awesomplete.ul).prepend(`
		// 		<div class="search-text">
		// 			<span class="search-text"></span>
		// 		<div>`
		// 	).find(".search-text");
		// }

		// search_text.html(`
		// 	<span class="flex justify-between">
		// 		<span class="ellipsis">Search for ${frappe.utils.xss_sanitise(txt).bold()}</span>
		// 		<kbd>↵</kbd>
		// 	</span>
		// `);

		// search_text.click(() => {
		// 	frappe.searchdialog.search.init_search(txt, "global_search");
		// });

		// REDESIGN TODO: Remove this as a selectable option
		if (txt.charAt(0) === "#") {
			return;
		}

		this.options.push({
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
			onclick: function () {
				frappe.searchdialog.search.init_search(txt, "global_search");
			},
		});
	}

	make_search_in_current(txt) {
		var route = frappe.get_route();
		if (route[0] === "List" && txt.indexOf(" in") === -1) {
			// search in title field
			const doctype = frappe.container.page?.list_view?.doctype;
			if (!doctype) return;
			var meta = frappe.get_meta(doctype);
			var search_field = meta.title_field || "name";
			var options = {};
			options[search_field] = ["like", "%" + txt + "%"];
			this.options.push({
				label: __("Find {0} in {1}", [
					frappe.utils.xss_sanitise(txt).bold(),
					__(route[1]).bold(),
				]),
				value: __("Find {0} in {1}", [txt, __(route[1])]),
				route_options: options,
				onclick: function () {
					cur_list.show();
				},
				index: 90,
				default: "Current",
				match: txt,
			});
		}
	}

	make_calculator(txt) {
		function getDecimalPlaces(num) {
			if (Math.floor(num) === num) return 0;
			return num.toString().split(".")[1].length || 0;
		}

		var first = txt.substr(0, 1);
		if (first == parseInt(first) || first === "(" || first === "=") {
			if (first === "=") {
				txt = txt.substr(1);
			}
			try {
				var val = eval(txt);

				// Split the input to find the numbers and their decimal places
				var numbers = txt.match(/[+-]?([0-9]*[.])?[0-9]+/g);
				var maxDecimalPlaces = 0;
				if (numbers) {
					maxDecimalPlaces = Math.max(
						...numbers.map((num) => getDecimalPlaces(parseFloat(num)))
					);
				}

				// Use a default precision of 2 decimal places if no decimal places are found
				if (maxDecimalPlaces === 0) {
					maxDecimalPlaces = 2;
				}

				// Adjust the result to the maximum number of decimal places found or default precision
				var rounded_val = parseFloat(val.toFixed(maxDecimalPlaces));

				var formatted_value = __("{0} = {1}", [txt, (rounded_val + "").bold()]);
				this.options.push({
					label: formatted_value,
					value: __("{0} = {1}", [txt, rounded_val]),
					match: rounded_val,
					index: 80,
					default: "Calculator",
					onclick: function () {
						frappe.msgprint(formatted_value, __("Result"));
					},
				});
			} catch (e) {
				// pass
			}
		}
	}

	make_random(txt) {
		if (txt.toLowerCase().includes("random")) {
			this.options.push({
				label: __("Generate Random Password"),
				value: frappe.utils.get_random(16),
				onclick: function () {
					frappe.msgprint(frappe.utils.get_random(16), __("Result"));
				},
			});
		}
	}
};
