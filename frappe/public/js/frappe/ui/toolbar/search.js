// Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.ui.toolbar.Search = frappe.ui.toolbar.SelectorDialog.extend({
	init: function() {
		this._super({
			title: __("Search"),
			execute: function(val) {
				frappe.set_route("List", val, {"name": "%"});
			},
			help: __("Shortcut") + ": Ctrl+G"
		});

		// get new types
		this.set_values(frappe.boot.user.can_search.join(',').split(','));
	}
});

frappe.search = {
	setup: function() {
		$("#navbar-search").autocomplete({
			minLength: 0,
			source: function(request, response) {
				var txt = strip(request.term);
				if(!txt) return;
				var lower = strip(txt.toLowerCase());
				frappe.search.options = [];
				$.each(frappe.search.verbs, function(i, action) {
					action(lower);
				});

				// sort options
				frappe.search.options.sort(function(a, b) {
					return a.match.length - b.match.length; });

				frappe.search.add_help();

				response(frappe.search.options);
			},
			focus: function(event, ui) {
				return false;
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
		}).data('ui-autocomplete')._renderItem = function(ul, d) {
			var html = "<span class='small'>" + __(d.value) + "</span>";
			if(d.description && d.value!==d.description) {
				html += '<br><span class="small text-muted">' + __(d.description) + '</span>';
			}
			return $('<li></li>')
				.data('item.autocomplete', d)
				.html('<a><p>' + html + '</p></a>')
				.appendTo(ul);
		};

		frappe.search.make_page_title_map();
	},
	add_help: function() {
		frappe.search.options.push({
			value: __("Help on Search"),
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
			frappe.search.options.push({
				value: __('Find {0} in {1}', ["<b>"+txt+"</b>", "<b>" + route[1] + "</b>"]),
				route_options: {"name": ["like", "%" + txt + "%"]},
				onclick: function() {
					frappe.container.page.doclistview.set_route_options();
				},
				match: txt
			});
		}
	},

	// recent
	function(txt) {
		for(var doctype in locals) {
			if(doctype[0]!==":" && !frappe.model.is_table(doctype)) {
				var ret = frappe.search.find(keys(locals[doctype]), txt, function(match) {
					return {
						value: __(doctype) + " <b>" + match + "</b>",
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
					value:__("New {0}", ["<b>"+match+"</b>"]),
					route:["Form", match, "New " + match]
				}
			});
		}
	},

	// doctype list
	function(txt) {
		frappe.search.find(frappe.boot.user.can_read, txt, function(match) {
			return {
				value: __("{0} List", ["<b>"+__(match)+"</b>"]),
				route:["List", match]
			}
		});
	},

	// pages
	function(txt) {
		frappe.search.find(keys(frappe.search.pages), txt, function(match) {
			return {
				value: __("Open {0}", ["<b>"+__(match)+"</b>"]),
				route: [frappe.search.pages[match].route || frappe.search.pages[match].name]
			}
		});
	},

	// modules
	function(txt) {
		frappe.search.find(keys(frappe.modules), txt, function(match) {
			ret = {
				value: __("Open {0}", ["<b>"+__(match)+"</b>"]),
			}
			if(frappe.modules[match].link) {
				ret.route = [frappe.modules[match].link];
			} else {
				ret.route = ["Module", "<b>"+match+"</b>"];
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
					value: __('Find {0} in {1}', ["<b>"+__(parts[0])+"</b>", "<b>"+__(match)+"</b>"]),
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
				frappe.search.options.push({
					value: $.format('{0} = {1}', [txt, "<b>"+val+"</b>"]),
					match: val,
					onclick: function(match) {
						msgprint(match, "Result");
					}
				});
			} catch(e) {
				// pass
			}

		};
	},
];
