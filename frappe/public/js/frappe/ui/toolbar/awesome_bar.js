// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt
frappe.provide('frappe.search');

frappe.search.AwesomeBar = Class.extend({
	setup: function(element) {
		var $input = $(element);
		var input = $input.get(0);
		var me = this;
		this.search = new frappe.search.Search();

		var awesomplete = new Awesomplete(input, {
			minChars: 0,
			maxItems: 99,
			autoFirst: true,
			list: [],
			filter: function (text, term) { 
				return true; 
			},
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
			me.options = [];

			if(txt) {
				me.build_options(strip(txt.toLowerCase()));
			}

			me.add_recent(txt || "");
			// console.log(me.options);
			awesomplete.list = me.options;

		});

		var open_recent = function() {
			if (!this.autocomplete_open) {
				$(this).trigger("input");
			}
		}
		$input.on("focus", open_recent);

		$input.on("awesomplete-open", function(e) {
			me.autocomplete_open = e.target;
		});

		$input.on("awesomplete-close", function(e) {
			me.autocomplete_open = false;
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
				console.log("onclick", item.onclick);
				console.log("match", item.match);
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

		this.make_page_title_map();
		this.setup_recent();

	},

	add_recent: function(txt) {
		var me = this;
		values = [];
		$.each(me.recent, function(i, doctype) {
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

		console.log("values", values);

		this.find(values, txt, function(match) {
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

	find: function(list, txt, process, prepend) {
		var me = this;
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
						me.options = option.concat(me.options);
					} else {
						me.options = me.options.concat(option);
					}
				}
			}
		});
	},
	
	make_page_title_map: function() {
		var me = this;
		this.pages = {};
		$.each(frappe.boot.page_info, function(name, p) {
			me.pages[p.title] = p;
			p.name = name;
		});
	},
	setup_recent: function() {
		this.recent = JSON.parse(frappe.boot.user.recent || "[]") || [];
	},
	is_present: function(txt, item) {
		($.isArray(item)) ?	_item = item[0] : _item = item;
		_item = __(_item || '').toLowerCase().replace(/-/g, " ");
		if(txt===_item || _item.indexOf(txt) !== -1) {
			return item;
		}
	},

	build_options: function(txt) {
		this.single_results = 
			this.make_global_search(txt).concat(
				this.make_search_in_current(txt),
				this.make_calculator(txt)
			);
		this.multi_results = 
			this.make_new_doc(txt).concat(
				this.make_search_in_list(txt),
				this.get_doctypes(txt),
				this.get_reports(txt),
				this.get_pages(txt),
				this.get_modules(txt)
			);

		this.options = this.single_results.concat(this.multi_results);
	},

	make_global_search: function(txt) {
		var me = this;
		return [{
			label: __("Search for '" + txt.bold() + "'"),
			value: __("Search for '" + txt + "'"),
			match: txt,
			onclick: function() {
				me.search.search_dialog.show();
				me.search.on_awesome_bar(txt);
			}
		}];
	},

	make_search_in_current: function(txt) {
		var route = frappe.get_route();
		if(route[0]==="List" && txt.indexOf(" in") === -1) {
			// search in title field
			var meta = frappe.get_meta(frappe.container.page.doclistview.doctype);
			var search_field = meta.title_field || "name";
			var options = {};
			options[search_field] = ["like", "%" + txt + "%"];
			return [{
				label: __('Find {0} in {1}', [txt.bold(), route[1].bold()]),
				value: __('Find {0} in {1}', [txt, route[1]]),
				route_options: options,
				onclick: function() {
					cur_list.refresh();
				},
				match: txt
			}];
		} else { return []; }
	},

	make_calculator: function(txt) {
		var first = txt.substr(0,1);
		if(first==parseInt(first) || first==="(" || first==="=") {
			if(first==="=") {
				txt = txt.substr(1);
			}
			try {
				var val = eval(txt);
				var formatted_value = __('{0} = {1}', [txt, (val + '').bold()]);
				return [{
					label: formatted_value,
					value: __('{0} = {1}', [txt, val]),
					match: val,
					onclick: function() {
						msgprint(formatted_value, "Result");
					}
				}];
			} catch(e) {
				// pass
			}
		} else { return []; }
	},

	make_new_doc: function(txt) {
		var me = this;
		var out = [];
		if(txt.split(" ")[0]==="new") {
			frappe.boot.user.can_create.forEach(function (item) {
				var target = me.is_present(txt.substr(4), item);
				if(target) {
					out.push({
						label: __("New {0}", [target.bold()]),
						value: __("New {0}", [target]),
						match: target,
						onclick: function() { frappe.new_doc(target, true); }
					});
				}
			});
		}
		return out;
	},

	make_search_in_list: function(txt) {
		var me = this;
		var out = [];
		if(in_list(txt.split(" "), "in")) {
			parts = txt.split(" in ");
			frappe.boot.user.can_read.forEach(function (item) {
				target = me.is_present(parts[1], item);
				if(target) {
					out.push({
						label: __('Find {0} in {1}', [__(parts[0]).bold(), __(target).bold()]),
						value: __('Find {0} in {1}', [__(parts[0]), __(target)]),
						route_options: {"name": ["like", "%" + parts[0] + "%"]},
						route: ["List", target]
					});
				}
			});
		}
		return out;
	},

	get_doctypes: function(txt) {
		var me = this;
		var out = [];

		var target;
		var option = function(type, route) {
			return {
				label: __("{0} " + type, [__(target).bold()]),
				value: __(target),
				route: route,
				match: target
			}
		}
		// shows options for a any second word
		frappe.boot.user.can_read.forEach(function (item) {
			target = me.is_present(txt, item);
			if(target) {
				// include 'making new' option
				if(in_list(frappe.boot.user.can_create, target)) {
					out.push({
						label: __("New {0}", [target.bold()]),
						value: __("New {0}", [target]),
						match: target,
						route: [""],
						onclick: function() { frappe.new_doc(target, true); }
					});
				}
				if(in_list(frappe.boot.single_types, target)) {
					out.push(option("Form", ["Form", target, target]));

				} else if(in_list(frappe.boot.treeviews, target)) {
					out.push(option("Tree", ["Tree", target]));

				} else {
					out.push(option("List", ["List", target]));

					if(frappe.model.can_get_report(target)) {
						out.push(option("Report", ["Report", target]));
					}
					if(frappe.boot.calendars.indexOf(target) !== -1) {
						out.push(option("Calendar", ["Calendar", target]));
						out.push(option("Gantt", ["List", target, "Gantt"]));
					}
				}

			}
		});
		return out;
	},

	get_reports: function(txt) {
		var me = this;
		var out = [];
		Object.keys(frappe.boot.user.all_reports).forEach(function(item) {
			var target = me.is_present(txt, item);
			if(target) {
				var report = frappe.boot.user.all_reports[target];

				var route = [];
				if(report.report_type == "Report Builder")
					route = ["Report", report.ref_doctype, target];
				else
					route = ["query-report",  target];

				out.push({
					label: __("Report {0}", [__(target).bold()]),
					value: __("Report {0}" , [__(target)]),
					match: txt,
					route: route
				});
			}
		});
		return out;
	},

	get_pages: function(txt) {
		var me = this;
		var out = [];
		Object.keys(this.pages).forEach(function(item) {
			var target = me.is_present(txt, item);
			if(target) {
				var page = me.pages[target];
				out.push({
					label: __("Open {0}", [__(target).bold()]),
					value: __("Open {0}", [__(target)]),
					match: txt,
					route: [page.route || page.name]
				});
			}
		});
		// calendar
		var target = 'Calendar';
		if(__('calendar').indexOf(txt.toLowerCase()) === 0) {
			out.push({
				label: __("Open {0}", [__(target).bold()]),
				value: __("Open {0}", [__(target)]),
				route: [target, 'Event'],
				match: target
			});
		}
		return out;
	},

	get_modules: function(txt) {
		var me = this;
		var out = [];
		Object.keys(frappe.modules).forEach(function(item) {
			var target = me.is_present(txt, item);
			if(target) {
				var module = frappe.modules[target];
				if(module._doctype) return;
				ret = {
					label: __("Open {0}", [__(target).bold()]),
					value: __("Open {0}", [__(target)]),
					match: txt
				}
				if(module.link) {
					ret.route = [module.link];
				} else {
					ret.route = ["Module", target];
				}
				out.push(ret);
			}
		});
		return out;
	},
	
});
