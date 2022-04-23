// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt
frappe.provide('frappe.search');
frappe.provide('frappe.tags');

frappe.search.awesomebar_providers = [];

frappe.search.AwesomeBar = class AwesomeBar {
	setup(element) {
		var me = this;

		$('.search-bar').removeClass('hidden');
		var $input = $(element);
		var input = $input.get(0);

		var awesomplete = new Awesomplete(input, {
			minChars: 0,
			maxItems: 99,
			autoFirst: true,
			list: [],
			filter: function(text, term) {
				return true;
			},
			data: function(item, input) {
				return {
					label: (item.index || ""),
					value: item.value
				};
			},
			item: function(item, term) {
				var d = this.get_item(item.value);
				var name = __(d.label || d.value);
				var html = '<span>' + name + '</span>';
				if(d.description && d.value!==d.description) {
					html += '<br><span class="text-muted ellipsis">' + __(d.description) + '</span>';
				}
				return $('<li></li>')
					.data('item.autocomplete', d)
					.html(`<a style="font-weight:normal">${html}</a>`)
					.get(0);
			},
			sort: function(a, b) {
				// HACK: label here is actually score/relevance
				return (b.label - a.label);
			}
		});

		// Added to aid UI testing of global search
		input.awesomplete = awesomplete;

		this.awesomplete = awesomplete;

		$input.on("input", frappe.utils.debounce(function(e) {
			let value = e.target.value;
			let txt = value.trim().replace(/\s\s+/g, ' ');

			let options = [];
			frappe.search.awesomebar_providers.forEach(provider => {
				try {
					const results = provider(txt);
					if (Array.isArray(results)) {
						options.push(...results);
					}
				} catch (e) {
					console.error(e);
				}
			});
			options.sort((a, b) => a.index - b.index);
			awesomplete.list = me.deduplicate(options);
		}, 100));

		var open_recent = function() {
			if (!this.autocomplete_open) {
				$(this).trigger("input");
			}
		};
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
			} else {
				frappe.set_route(item.route);
			}
			$input.val("");
		});

		$input.on("awesomplete-selectcomplete", function(e) {
			$input.val("");
		});

		$input.on('keydown', (e) => {
			if (e.key == 'Escape') {
				$input.trigger('blur');
			}
		})
		frappe.search.utils.setup_recent();
		frappe.tags.utils.fetch_tags();
	}

	deduplicate(options) {
		var out = [], routes = [];
		options.forEach(function(option) {
			if(option.route) {
				if (
					option.route[0] === "List" &&
					option.route[2] !== 'Report' &&
					option.route[2] !== 'Inbox'
				) {
					option.route.splice(2);
				}

				var str_route = (typeof option.route==='string') ?
					option.route : option.route.join('/');
				if(routes.indexOf(str_route)===-1) {
					out.push(option);
					routes.push(str_route);
				} else {
					var old = routes.indexOf(str_route);
					if(out[old].index < option.index && !option.recent) {
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
};
