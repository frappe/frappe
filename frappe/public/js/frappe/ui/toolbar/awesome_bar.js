// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.search = {
	setup: function() {
		var opts = {
			autoFocus: true,
			minLength: 0,
			source: function(request, response) {
				var txt = strip(request.term);
				frappe.search.options = [];
				if(!txt) {
					// search recent
					frappe.search.verbs[1]("");
				} else {
					var lower = strip(txt.toLowerCase());
					$.each(frappe.search.verbs, function(i, action) {
						action(lower);
					});
				}

				// sort options
				frappe.search.options.sort(function(a, b) {
					return (a.match || "").length - (b.match || "").length; });

				frappe.search.add_help();

				response(frappe.search.options);
			},
			open: function() {
				frappe.search.autocomplete_open = true;
			},
			close: function() {
				frappe.search.autocomplete_open = false;
			},
			select: function(event, ui) {
				if(ui.item.route_options) {
					frappe.route_options = ui.item.route_options;
				}

				if(ui.item.onclick) {
					ui.item.onclick(ui.item.match);
				} else {
					frappe.set_route(ui.item.route);
				}
				$(this).val('');
				return false;
			}
		};

		var render_item = function(ul, d) {
			var html = "<span>" + __(d.label || d.value) + "</span>";
			if(d.description && d.value!==d.description) {
				html += '<br><span class="text-muted">' + __(d.description) + '</span>';
			}
			return $('<li></li>')
				.data('item.autocomplete', d)
				.html('<a><p>' + html + '</p></a>')
				.appendTo(ul);
		};

		var open_recent = function() {
			if (!frappe.search.autocomplete_open) {
				$(this).autocomplete("search", "");
			}
		}

		$("#navbar-search")
			.on("focus", open_recent)
			.autocomplete(opts).data('ui-autocomplete')._renderItem = render_item;

		$("#sidebar-search")
			.on("focus", open_recent)
			.autocomplete(opts).data('ui-autocomplete')._renderItem = render_item;

		frappe.search.make_page_title_map();
		frappe.search.setup_recent();
	},
	add_help: function() {
		frappe.search.options.push({
			label: __("Help on Search"),
			onclick: function() {
				var txt = '<table class="table table-bordered">\
					<tr><td style="width: 50%">'+__("Make a new record")+'</td><td>'+
						__("<b>new</b> <i>type of document</i>")+'</td></tr>\
					<tr><td>'+__("List a document type")+'</td><td>'+
						__("<i>document type...</i>, e.g. <b>customer</b>")+'</td></tr>\
					<tr><td>'+__("Search in a document type")+'</td><td>'+
						__("<i>text</i> <b>in</b> <i>document type</i>")+'</td></tr>\
					<tr><td>'+__("Open a module or tool")+'</td><td>'+
						__("<i>module name...</i>")+'</td></tr>\
					<tr><td>'+__("Calculate")+'</td><td>'+
						__("<i>e.g. <strong>(55 + 434) / 4</strong> or <strong>=Math.sin(Math.PI/2)</strong>...</i>")+'</td></tr>\
				</table>'
				msgprint(txt, "Search Help");
			}
		});
	},
	make_page_title_map: function() {
		frappe.search.pages = {};
		$.each(frappe.boot.page_info, function(name, p) {
			frappe.search.pages[p.title] = p;
			p.name = name;
		});
	},
	setup_recent: function() {
		var recent = JSON.parse(frappe.boot.user.recent || "[]") || [];
		frappe.search.recent = {};
		for (var i=0, l=recent.length; i < l; i++) {
			var d = recent[i];
			if (!(d[0] && d[1])) continue;

			if (!frappe.search.recent[d[0]]) {
				frappe.search.recent[d[0]] = [];
			}
			frappe.search.recent[d[0]].push(d[1]);
		}
	},
	find: function(list, txt, process) {
		$.each(list, function(i, item) {
			_item = __(item).toLowerCase().replace(/-/g, " ");
			if(txt===_item || _item.indexOf(txt) !== -1) {
				var option = process(item);
				option.match = item;
				frappe.search.options.push(option);
			}
		});
	}
}

frappe.search.verbs = [
	// search in list if current
	function(txt) {
		var route = frappe.get_route();
		if(route[0]==="List" && txt.indexOf(" in") === -1) {
			// search in title field
			var meta = frappe.get_meta(frappe.container.page.doclistview.doctype);
			var search_field = meta.title_field || "name";
			var options = {};
			options[search_field] = ["like", "%" + txt + "%"];
			frappe.search.options.push({
				label: __('Find {0} in {1}', ["<b>"+txt+"</b>", "<b>" + route[1] + "</b>"]),
				value: __('Find {0} in {1}', [txt, route[1]]),
				route_options: options,
				onclick: function() {
					frappe.container.page.doclistview.set_route_options();
				},
				match: txt
			});
		}
	},

	// recent
	function(txt) {
		var doctypes = frappe.utils.unique(keys(locals).concat(keys(frappe.search.recent)));
		for(var i in doctypes) {
			var doctype = doctypes[i];
			if(doctype[0]!==":" && !frappe.model.is_table(doctype)
				&& !in_list(frappe.boot.single_types, doctype)
				&& !in_list(["DocType", "DocField", "DocPerm", "Page", "Country",
					"Currency", "Page Role", "Print Format"], doctype)) {

				var values = frappe.utils.remove_nulls(frappe.utils.unique(
					keys(locals[doctype]).concat(frappe.search.recent[doctype] || [])
				));

				var ret = frappe.search.find(values, txt, function(match) {
					return {
						label: __(doctype) + " <b>" + match + "</b>",
						value: __(doctype) + " " + match,
						route: ["Form", doctype, match]
					}
				});
			}
		}
	},

	// new doc
	function(txt) {
		var ret = false;
		if(txt.split(" ")[0]==="new") {
			frappe.search.find(frappe.boot.user.can_create, txt.substr(4), function(match) {
				return {
					label: __("New {0}", ["<b>"+match+"</b>"]),
					value: __("New {0}", [match]),
					onclick: function() { new_doc(match); }
				}
			});
		}
	},

	// doctype list
	function(txt) {
		frappe.search.find(frappe.boot.user.can_read, txt, function(match) {
			if(in_list(frappe.boot.single_types, match)) {
				return {
					label: __("{0}", ["<b>"+__(match)+"</b>"]),
					value: __(match),
					route:["Form", match, match]
				}
			} else {
				return {
					label: __("{0} List", ["<b>"+__(match)+"</b>"]),
					value: __("{0} List", [__(match)]),
					route:["List", match]
				}
			}
		});
	},

	// pages
	function(txt) {
		frappe.search.find(keys(frappe.search.pages), txt, function(match) {
			return {
				label: __("Open {0}", ["<b>"+__(match)+"</b>"]),
				value: __("Open {0}", [__(match)]),
				route: [frappe.search.pages[match].route || frappe.search.pages[match].name]
			}
		});
	},

	// modules
	function(txt) {
		frappe.search.find(keys(frappe.modules), txt, function(match) {
			ret = {
				label: __("Open {0}", ["<b>"+__(match)+"</b>"]),
				value: __("Open {0}", [__(match)]),
			}
			if(frappe.modules[match].link) {
				ret.route = [frappe.modules[match].link];
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
			frappe.search.find(frappe.boot.user.can_read, parts[1], function(match) {
				return {
					label: __('Find {0} in {1}', ["<b>"+__(parts[0])+"</b>", "<b>"+__(match)+"</b>"]),
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
				var formatted_value = __('{0} = {1}', [txt, "<b>"+val+"</b>"]);
				frappe.search.options.push({
					label: formatted_value,
					value: __('{0} = {1}', [txt, val]),
					match: val,
					onclick: function(match) {
						msgprint(formatted_value, "Result");
					}
				});
			} catch(e) {
				// pass
			}

		};
	},
];
