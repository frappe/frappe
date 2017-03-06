frappe.provide('frappe.search');

frappe.search.utils = {
    // Find stuff
    get_doctypes: function(keywords, view = "") {

    },

    get_creatables: function(keywords) {

    },

    get_reports: function(keywords) {
        var me = this;
		var out = [];
		Object.keys(frappe.boot.user.all_reports).forEach(function(item) {
			var level = me.fuzzy_search(keywords, item);
			if(level > 0) {
				var report = frappe.boot.user.all_reports[item];
				if(report.report_type == "Report Builder")
					route = ["Report", report.ref_doctype, item];
				else
					route = ["query-report",  item];
				out.push({
                    type: "Report",
					label: rendered_label,
					value: __("Report {0}" , [__(item)]),
					match: keywords,
                    // ???
					index: index,
					route: route
				});
			}
		});
		return out;
    },

    get_pages: function(keywords) {

    },

    get_modules: function(keywords) {

    },

    get_all_global_results: function (keywords, start, limit, callback, condensed = 0) {
        var me = this;

        function get_results_sets(data) {
            var results_sets = [], result, set;
            var get_existing_set = function(doctype) {
                return results_sets.find(function(set) {
                    return set.title === doctype;
                });
            }
            data.forEach(function(d) {
                // Condition for condensed
                result = {
                    label: d.name,
                    value: d.name,
                    description: d.content,
                    route: ['Form', d.doctype, d.name]
                }
                set = get_existing_set(d.doctype);
                if(set) {
                    set.results.push(result);
                } else {
                    set = {
                        title: d.doctype,
                        results: [result]
                    }
                    results_sets.push(set);
                }

            });
            return results_sets;
        }

		frappe.call({
			method: "frappe.utils.global_search.search",
			args: {
				text: keywords,
				start: start,
				limit: limit,
			},
			callback: function(r) {
				if(r.message) {
                    // console.log(get_results_sets(r.message));
                    callback(get_results_sets(r.message), keywords);
				}
			}
		});
    },

    get_doctype_globals: function(doctype, keywords, start, limit, callback) {
        var me = this;
		frappe.call({
			method: "frappe.utils.global_search.search_in_doctype",
			args: {
				doctype: doctype,
				text: keywords,
				start: start,
				limit: limit,
			},
			callback: function(r) {
				if(r.message) {
                    callback(r);
				}
			}
		});
    },

    get_help_results: function(keywords) {

    },

    get_recent_pages: function(keywords) {

    },

    get_frequent_pages: function(keywords) {

    },

    get_calculator: function(expression) {

    },

    commands: {
        // single-arg
        cmd_report: function(keywords) {
            // everything reports

        },
        cmd_new: function(keywords) {

        },
        cmd_gantt: function(keywords) {

        },
        cmd_calendar: function(keywords) {

        },
        cmd_tree: function(keywords) {

        },

        // multi-arg
        cmd_in: function(doc, doctype) {

        },
    },

    // Find stuff given a condition
    parse_keyword_and_trigger_results: function(input) {

    },

    // Generic: (and neatly categorised and ranked)
    get_all_results: function(keywords) {

    },

    // Utils
    fuzzy_search: function(keywords, _item) {

        // Allow for case sensitive
        // return only level
		item = __(_item || '').toLowerCase().replace(/-/g, " ");

		keywords = keywords.toLowerCase();

		var ilen = item.length;
		var tlen = keywords.length;
		var match_level = tlen/ilen;
		var rendered_label = "";
		var i, j, skips = 0, mismatches = 0;

		if (tlen > ilen) {
			return [];
		}
		if (item.indexOf(keywords) !== -1) {
			var regEx = new RegExp("("+ keywords +")", "ig");
			rendered_label = _item.replace(regEx, '<b>$1</b>');
			return [_item, ilen/50, rendered_label];
		}
		outer: for (i = 0, j = 0; i < tlen; i++) {
			var t_ch = keywords.charCodeAt(i);
			if(mismatches !== 0) skips++;
			if(skips > 3) return [];
			mismatches = 0;
			while (j < ilen) {
				var i_ch = item.charCodeAt(j);
				if (i_ch === t_ch) {
					var item_char =  _item.charAt(j);
					if(item_char === item_char.toLowerCase()){
						rendered_label += '<b>' + keywords.charAt(i) + '</b>';
					} else {
						rendered_label += '<b>' + keywords.charAt(i).toUpperCase() + '</b>';
					}
					j++;
					continue outer;
				}
				mismatches++;
				if(mismatches > 2) return [];
				rendered_label += _item.charAt(j);
				j++;
			}
			return [];
		}
		rendered_label += _item.slice(j);
		return [_item, 20 + ilen/50, rendered_label];
	},

    replace_with_bold: function(string, subsequence) {
        // if fuzzy_returns zero, return plain string

        // if above 0.5, use regEx

        // if below 0.5, replace the long way

    }
}