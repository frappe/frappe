// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt
frappe.provide("frappe.search");
frappe.provide("frappe.tags");

frappe.search.AwesomeBar = class AwesomeBar {
	setup(element) {
		$(".search-bar, .navbar-search-bar").removeClass("hidden");

		this.options = [];
		this.global_results = [];

		this.setup_search_modal(element);

		frappe.search.utils.setup_recent();
	}

	setup_search_modal(element) {
		let is_event_listeners_added = false;
		let $search_element = $(element);

		let search_modal = new frappe.get_modal("Search", "");

		search_modal.removeClass("fade");
		search_modal.on("shown.bs.modal", () => {
			const input = search_modal.find("#navbar-search").get(0);
			setTimeout(() => input.focus(), 10);
		});

		let search_modal_body = `<div class="align-baseline flex py-2 px-1 relative navbar-modal-wrapper">
			<div class="modal-search-icon absolute pr-2 pl-2">${frappe.utils.icon("search")}</div>
			<input
				id="navbar-search"
				type="text"
				class="form-control bg-transparent shadow-none" aria-haspopup="true"
				placeholder="${__("Search or type a command")}" autocomplete="off"
			/>
			<div class="modal-divider"></div>
		</div>`;

		let search_modal_footer = `<div class="awesomebar-modal-footer flex justify-between w-100">
			<div class="help-navigation">
				<span class="help-item-navigate">
					<span class="help-item">${frappe.utils.icon("arrow-up")}</span>
					<span class="help-item">${frappe.utils.icon("arrow-down")}</span>
					<span>${__("to navigate")}</span>
				</span>
				<span class="help-item-navigate">
					<span class="help-item">${frappe.utils.icon("corner-down-left")}</span>
					<span>${__("to select")}</span>
				</span>
				<span class="help-item help-item-esc">${__("esc")}</span>
				<span>${__("to close")}</span>
			</div>
			<div class="pointer">${frappe.utils.icon("circle-question-mark")}</div>
		</div>`;

		search_modal.find(".modal-body").css("padding", "0").html(search_modal_body);
		search_modal.find(".modal-header").css("display", "none");
		search_modal
			.find(".modal-footer")
			.removeClass("hide")
			.addClass("cool-awesomebar-modal-footer")
			.html(search_modal_footer);
		search_modal.find(".pointer").on("click", () => {
			this.show_help();
		});

		$search_element.on("click", () => {
			search_modal.modal("show");

			if (is_event_listeners_added) return;
			is_event_listeners_added = true;

			this.setup_event_listeners(search_modal);
		});
	}

	setup_event_listeners(search_modal) {
		var me = this;
		let $input = search_modal.find("#navbar-search");
		let input = $input.get(0);

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
				if (d.type == "Desktop Icon") {
					target = frappe.utils.get_route_for_icon(d.icon_data);
					d.route = target;
					d.route_options = {
						sidebar: d.icon_data.label,
					};
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

				awesomplete.list = me.deduplicate(me.options);
			}, 50)
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
				if (item.route && item.route[0].startsWith("https://")) {
					window.open(item.route[0], "_blank");
					return;
				}
				frappe.set_route(item.route);
			}
			$input.val("");
			$input.trigger("blur");
			search_modal.modal("hide");
		});

		$input.on("awesomplete-selectcomplete", function (e) {
			$input.val("");
		});

		$input.on("keydown", (e) => {
			if (e.key == "Escape") {
				$input.trigger("blur");
			}
		});
	}

	show_help() {
		const txt =
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
			__("Open in new tab") +
			"</td><td>" +
			(frappe.utils.is_mac() ? "⌘ + Enter" : "Ctrl + Enter") +
			"</td></tr>\
			<tr><td>" +
			__("Calculate") +
			"</td><td>" +
			__("e.g. (55 + 434) / 4 or =Math.sin(Math.PI/2)...") +
			"</td></tr>\
		</table>";
		frappe.msgprint(txt, __("Search Help"));
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
				frappe.search.utils.get_desktop_icons(txt),
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
			value: __("Search for {0}", [frappe.utils.xss_sanitise(txt)]),
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
				value: __("Find {0} in {1}", [frappe.utils.xss_sanitise(txt), __(route[1])]),
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
		const decimalStr = get_number_format_info().decimal_str;
		const first = txt.substr(0, 1);

		if (first == parseInt(first) || first === "(" || first === "=") {
			if (first === "=") {
				txt = txt.substr(1);
			}
			try {
				// Split the input to find the numbers and their decimal places
				const numbers = txt.match(/[+-]?([0-9]*[.,])?[0-9]+/g);

				let maxDecimalPlaces = 0;
				if (numbers) {
					maxDecimalPlaces = Math.max(
						...numbers.map((num) => num.split(decimalStr)[1]?.length || 0)
					);
				}

				// Find the result to the appropriate number of decimal places
				const val = frappe.utils.eval_expression(txt);
				const result = format_number(val, null, maxDecimalPlaces);
				const formatted_value = __("{0} = {1}", [
					frappe.utils.xss_sanitise(txt),
					result.bold(),
				]);
				this.options.push({
					label: formatted_value,
					value: __("{0} = {1}", [frappe.utils.xss_sanitise(txt), result]),
					match: result,
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
