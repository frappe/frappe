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
						</table>'
						msgprint(txt, "Search Help");
					}
				});

				response(frappe.search.options);
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
				setTimeout(function() { $("#navbar-search").val(""); }, 100);
			}
		}).data('ui-autocomplete')._renderItem = function(ul, d) {
			var html = "<strong class='small'>" + d.value + "</strong>";
			if(d.description && d.value!==d.description) {
				html += '<br><span class="small text-muted">' + d.description + '</span>';
			}
			return $('<li></li>')
				.data('item.autocomplete', d)
				.html('<a><p>' + html + '</p></a>')
				.appendTo(ul);
		};;
	},
	find: function(list, txt, process) {
		var ret = null;
		$.each(list, function(i, item) {
			_item = __(item).toLowerCase().replace(/-/g, " ");
			if(txt===_item || _item.indexOf(txt) !== -1) {
				var option = process(item);
				option.match = item;
				frappe.search.options.push(option);
			}
		});
		return ret;
	}
}

frappe.search.verbs = [
	// search in list if current
	function(txt) {
		var route = frappe.get_route();
		if(route[0]==="List") {
			frappe.search.options.push({
				value: __('Find "{0}" in {1}', [txt, route[1]]),
				route_options: {"name": ["like", "%" + txt + "%"]},
				onclick: function() {
					frappe.container.page.doclistview.set_route_options();
				},
				match: txt
			});
		}
	},

	// new doc
	function(txt) {
		var ret = false;
		if(txt.split(" ")[0]==="new") {
			frappe.search.find(frappe.boot.user.can_create, txt.substr(4), function(match) {
				return {
					value:__("New {0}", [match]),
					route:["Form", match, "New " + match]
				}
			});
		}
	},

	// doctype list
	function(txt) {
		frappe.search.find(frappe.boot.user.can_read, txt, function(match) {
			return {
				value: __("{0} List", [match]),
				route:["List", match]
			}
		});
	},

	// pages
	function(txt) {
		frappe.search.find(keys(frappe.boot.page_info), txt, function(match) {
			return {
				value: __("Open {0}", [match]),
				route: [match]
			}
		});
	},

	// modules
	function(txt) {
		frappe.search.find(keys(frappe.modules), txt, function(match) {
			ret = {
				value: __("Open {0}", [match]),
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
					value: __('Find "{0}" in {1}', [parts[0], match]),
					route_options: {"name": ["like", "%" + parts[0] + "%"]},
					route: ["List", match]
				}
			});
		}
	},
];
