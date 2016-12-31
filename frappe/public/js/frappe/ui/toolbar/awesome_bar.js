// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt
frappe.provide('frappe.search');

frappe.awesome_bar = {
	setup: function(element) {
		var $input = $(element);
		var input = $input.get(0);
		frappe.awesome_bar.global_search = new frappe.search.Global("Global Search");

		var awesomplete = new Awesomplete(input, {
			minChars: 0,
			maxItems: 99,
			autoFirst: true,
			list: [],
			filter: function (text, term) { return true; },
			item: function(item, term) {
				var d = item;
				var html = "<span>" + __(d.label || d.value) + "</span>";
				if(d.description && d.value!==d.description) {
					html += '<br><span class="text-muted">' + __(d.description) + '</span>';
				}
				return $('<li></li>')
					.data('item.autocomplete', d)
					.html('<a style="font-weight:normal"><p>' + html + '</p></a>')
					.get(0);
			},
			sort: function(a, b) { return 0; }
		});

		$input.on("input", function(e) {
			var value = e.target.value;
			var txt = strip(value);
			frappe.awesome_bar.options = [];
			if(txt) {
				var lower = strip(txt.toLowerCase());
				$.each(frappe.awesome_bar.verbs, function(i, action) {
					action(lower);
				});
			}

			// sort options
			frappe.awesome_bar.options.sort(function(a, b) {
				return (a.match || "").length - (b.match || "").length; });

			frappe.awesome_bar.add_recent(txt || "");
			frappe.awesome_bar.add_help();

			// de-duplicate
			var out = [], routes = [];
			frappe.awesome_bar.options.forEach(function(option) {
				if(option.route) {
					var str_route = (typeof option.route==='string') ?
							option.route : option.route.join('/');
					if(routes.indexOf(str_route)===-1) {
						out.push(option);
						routes.push(str_route);
					}
				} else {
					out.push(option);
				}
			});
			awesomplete.list = out;
		});

		var open_recent = function() {
			if (!frappe.awesome_bar.autocomplete_open) {
				$(this).trigger("input");
			}
		}
		$input.on("focus", open_recent);

		$input.on("awesomplete-open", function(e) {
			frappe.awesome_bar.autocomplete_open = e.target;
		});

		$input.on("awesomplete-close", function(e) {
			frappe.awesome_bar.autocomplete_open = false;
		});

		$input.on("awesomplete-select", function(e) {
			var o = e.originalEvent;
			var value = o.text.value;
			var item = awesomplete.get_item(value);

			if(item.route_options) {
				frappe.route_options = item.route_options;
			}

			if(item.onclick) {
				item.onclick(item.match);
			} else {
				var previous_hash = window.location.hash;
				frappe.set_route(item.route);

				// hashchange didn't fire!
				if (window.location.hash == previous_hash) {
					frappe.route();
				}
			}
		});

		$input.on("awesomplete-selectcomplete", function(e) {
			$input.val("");
		});

		frappe.awesome_bar.make_page_title_map();
		frappe.awesome_bar.setup_recent();
		frappe.awesome_bar.global_search.setup("Global Search");
	},
	add_help: function() {
		frappe.awesome_bar.options.push({
			label: __("Help on Search"),
			value: "Help on Search",
			onclick: function() {
				var txt = '<table class="table table-bordered">\
					<tr><td style="width: 50%">'+__("Make a new record")+'</td><td>'+
						__("new type of document")+'</td></tr>\
					<tr><td>'+__("List a document type")+'</td><td>'+
						__("document type..., e.g. customer")+'</td></tr>\
					<tr><td>'+__("Search in a document type")+'</td><td>'+
						__("text in document type")+'</td></tr>\
					<tr><td>'+__("Open a module or tool")+'</td><td>'+
						__("module name...")+'</td></tr>\
					<tr><td>'+__("Calculate")+'</td><td>'+
						__("e.g. (55 + 434) / 4 or =Math.sin(Math.PI/2)...")+'</td></tr>\
				</table>'
				msgprint(txt, "Search Help");
			}
		});
	},
	add_recent: function(txt) {
		values = [];
		$.each(frappe.awesome_bar.recent, function(i, doctype) {
			values.push([doctype[1], ['Form', doctype[0], doctype[1]]]);
		});

		values = values.reverse();

		$.each(frappe.route_history, function(i, route) {
			if(route[0]==='Form') {
				values.push([route[2], route]);
			}
			else if(in_list(['List', 'Report', 'Tree', 'modules', 'query-report'], route[0])) {
				if(route[1]) {
					values.push([route[1], route]);
				}
			}
			else if(route[0]) {
				values.push([frappe.route_titles[route[0]] || route[0], route]);
			}
		});

		frappe.awesome_bar.find(values, txt, function(match) {
			out = {
				route: match[1]
			}
			if(match[1][0]==='Form') {
				out.label = __(match[1][1]) + " " + match[1][2].bold();
				out.value = __(match[1][1]) + " " + match[1][2];
			} else if(in_list(['List', 'Report', 'Tree', 'modules', 'query-report'], match[1][0])) {
				var type = match[1][0], label = type;
				if(type==='modules') label = 'Module';
				else if(type==='query-report') label = 'Report';
				out.label = __(match[1][1]).bold() + " " + __(label);
				out.value = __(match[1][1]) + " " + __(label);
			} else {
				out.label = match[0].bold();
				out.value = match[0];
			}
			return out;
		}, true);
	},
	make_page_title_map: function() {
		frappe.awesome_bar.pages = {};
		$.each(frappe.boot.page_info, function(name, p) {
			frappe.awesome_bar.pages[p.title] = p;
			p.name = name;
		});
	},
	setup_recent: function() {
		frappe.awesome_bar.recent = JSON.parse(frappe.boot.user.recent || "[]") || [];
	},
	find: function(list, txt, process, prepend) {
		$.each(list, function(i, item) {
			if($.isArray(item)) {
				_item = item[0];
			} else {
				_item = item;
			}
			_item = __(_item || '').toLowerCase().replace(/-/g, " ");
			if(txt===_item || _item.indexOf(txt) !== -1) {
				var option = process(item);

				if(option) {
					if($.isPlainObject(option)) {
						option = [option];
					}

					option.forEach(function(o) { o.match = item; });

					if(prepend) {
						frappe.awesome_bar.options = option.concat(frappe.awesome_bar.options);
					} else {
						frappe.awesome_bar.options = frappe.awesome_bar.options.concat(option);
					}
				}
			}
		});
	},

}

frappe.awesome_bar.verbs = [

	// Global Search
	// But shows up at the very top
	function(txt) {
		frappe.awesome_bar.options.unshift({
			label: __("Search in Global Search: " + txt.bold()),
			value: __("Search in Global Search: " + txt.bold()),
			onclick: function(match) {
					try {
						frappe.awesome_bar.global_search.search_dialog.show();
						//$(".search-modal input").val("");
						frappe.awesome_bar.global_search.get_results(txt);
					} catch(e) {
						console.log(e);
					}
			}
		});
	},

	// search in list if current
	function(txt) {
		var route = frappe.get_route();
		if(route[0]==="List" && txt.indexOf(" in") === -1) {
			// search in title field
			var meta = frappe.get_meta(frappe.container.page.doclistview.doctype);
			var search_field = meta.title_field || "name";
			var options = {};
			options[search_field] = ["like", "%" + txt + "%"];
			frappe.awesome_bar.options.push({
				label: __('Find {0} in {1}', [txt.bold(), route[1].bold()]),
				value: __('Find {0} in {1}', [txt, route[1]]),
				route_options: options,
				onclick: function() {
					cur_list.refresh();
				},
				match: txt
			});
		}
	},

	// new doc
	function(txt) {
		var ret = false;
		if(txt.split(" ")[0]==="new") {
			frappe.awesome_bar.find(frappe.boot.user.can_create, txt.substr(4), function(match) {
				return {
					label: __("New {0}", [match.bold()]),
					value: __("New {0}", [match]),
					onclick: function() { frappe.new_doc(match, true); }
				}
			});
		}
	},

	// doctype list
	function(txt) {
		if (txt.toLowerCase().indexOf(" list")) {
			// remove list keyword
			txt = txt.replace(/ list/ig, "").trim();
		}

		frappe.awesome_bar.find(frappe.boot.user.can_read, txt, function(match) {
			if(in_list(frappe.boot.single_types, match)) {
				return {
					label: __("{0}", [__(match).bold()]),
					value: __(match),
					route:["Form", match, match]
				}
			} else if(in_list(frappe.boot.treeviews, match)) {
				return {
					label: __("{0} Tree", [__(match).bold()]),
					value: __(match),
					route:["Tree", match]
				}
			} else {
				out = [
					{
						label: __("{0} List", [__(match).bold()]),
						value: __("{0} List", [__(match)]),
						route:["List", match]
					},
				];
				if(frappe.model.can_get_report(match)) {
					out.push({
						label: __("{0} Report", [__(match).bold()]),
						value: __("{0} Report", [__(match)]),
						route:["Report", match]
					});
				}
				if(frappe.boot.calendars.indexOf(match) !== -1) {
					out.push({
						label: __("{0} Calendar", [__(match).bold()]),
						value: __("{0} Calendar", [__(match)]),
						route:["List", match, "Calendar"]
					});

					out.push({
						label: __("{0} Gantt", [__(match).bold()]),
						value: __("{0} Gantt", [__(match)]),
						route:["List", match, "Gantt"]
					});
				}
				return out;
			}
		});
	},

	// reports
	function(txt) {
		frappe.awesome_bar.find(keys(frappe.boot.user.all_reports), txt, function(match) {
			//console.log("Reports", (frappe.boot.user.all_reports));
			var report = frappe.boot.user.all_reports[match];
			var route = [];
			
			if(report.report_type == "Report Builder")
				route = ["Report", report.ref_doctype, match];
			else
				route = ["query-report",  match];

			return {
				label: __("Report {0}", [__(match).bold()]),
				value: __("Report {0}", [__(match)]),
				route: route
			}
		});
	},

	// pages
	function(txt) {
		frappe.awesome_bar.find(keys(frappe.awesome_bar.pages), txt, function(match) {
			//console.log("Pages", frappe.awesome_bar.pages)
			return {
				label: __("Open {0}", [__(match).bold()]),
				value: __("Open {0}", [__(match)]),
				route: [frappe.awesome_bar.pages[match].route || frappe.awesome_bar.pages[match].name]
			}
		});

		// calendar
		var match = 'Calendar';
		if(__('calendar').indexOf(txt.toLowerCase()) === 0) {
			frappe.awesome_bar.options.push({
				label: __("Open {0}", [__(match).bold()]),
				value: __("Open {0}", [__(match)]),
				route: ['List', 'Event', 'Calendar'],
				match: match
			});
		}
	},

	// modules
	function(txt) {
		frappe.awesome_bar.find(keys(frappe.modules), txt, function(match) {
			var module = frappe.modules[match];

			if(module._doctype) return;

			ret = {
				label: __("Open {0}", [__(match).bold()]),
				value: __("Open {0}", [__(match)]),
			}
			if(module.link) {
				ret.route = [module.link];
			} else {
				ret.route = ["Module", match];
			}
			return ret;
		});
	},

	// in
	function(txt) {
		if(in_list(txt.split(" "), "in")) {
			parts = txt.split(" in ");
			frappe.awesome_bar.find(frappe.boot.user.can_read, parts[1], function(match) {
				//console.log("Can read: ", frappe.boot.user.can_read);
				return {
					label: __('Find {0} in {1}', [__(parts[0]).bold(), __(match).bold()]),
					value: __('Find {0} in {1}', [__(parts[0]), __(match)]),
					route_options: {"name": ["like", "%" + parts[0] + "%"]},
					route: ["List", match]
				}
			});
		}
	},

	// calculator
	function(txt) {
		var first = txt.substr(0,1);
		if(first==parseInt(first) || first==="(" || first==="=") {
			if(first==="=") {
				txt = txt.substr(1);
			}

			try {
				var val = eval(txt);
				var formatted_value = __('{0} = {1}', [txt, (val + '').bold()]);
				frappe.awesome_bar.options.push({
					label: formatted_value,
					value: __('{0} = {1}', [txt, val]),
					match: val,
					onclick: function(match) {
						//console.log("match1 ", match);
						msgprint(formatted_value, "Result");
					}
				});
			} catch(e) {
				// pass
			}

		};
	},
];

