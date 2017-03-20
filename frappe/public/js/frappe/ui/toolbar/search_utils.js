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
        var me = this;
		var out = [];
		Object.keys(frappe.modules).forEach(function(item) {
			var level = me.fuzzy_search(txt, item);
			if(level > 0) {
				var module = frappe.modules[item];
				if(module._doctype) return;
				ret = {
					label: rendered_label,
					value: __("Open {0}", [__(item)]),
					match: txt,
					index: index,
					type: "Module",
					prefix: "Open"
				}
				if(module.link) {
					ret.route = [module.link];
				} else {
					ret.route = ["Module", item];
				}
				out.push(ret);
			}
		});
		return out;
    },

    get_all_global_results: function (keywords, start, limit, condensed = 0) {
        return new Promise(function(resolve, reject) {
            function get_results_sets(data) {
                var results_sets = [], result, set;
                var get_existing_set = function(doctype) {
                    return results_sets.find(function(set) {
                        return set.title === doctype;
                    });
                }
                data.forEach(function(d) {
                    // Condition for condensed
                    // more properties
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
                        resolve(get_results_sets(r.message));
                    } else {
                        resolve([]);
                    }
                }
            });
        });
    },

    get_doctype_globals: function(doctype, keywords, start, limit) {
        return new Promise(function(resolve, reject) {
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
                        resolve(r);
                    } else {
                        resolve([]);
                    }
                }
            });
        });
    },

    get_help_results: function(keywords) {
        function get_results_set(data) {
            var result;
            var set = {
                title: "Help",
                results: []
            }
            data.forEach(function(d) {
                // more properties
                result = {
                    label: d[0],
                    value: d[0],
                    description: d[1],
                    route:[],
                    data_path: d[2],
                    onclick: function() {

                    }
                }
                set.results.push(result);
            });
            return [set];
        }
        return new Promise(function(resolve, reject) {
            frappe.call({
                method: "frappe.utils.help.get_help",
                args: {
                    text: keywords
                },
                callback: function(r) {
                    if(r.message) {
                        resolve(get_results_set(r.message));
                    } else {
                        resolve([]);
                    }
                }
            });
        });
    },

    get_forum_results: function(keywords) {
        // WOAHH ...
        var me = this;
        function get_results_set(data) {
            var result;
            var set = {
                title: "Forum",
                results: []
            }
            data.forEach(function(d) {
                // more properties
                result = {
                    label: me.reverse_scrub(d.topic_slug),
                    value: "",
                    description: d.blurb,
                    route:[],
                    url: "",
                    onclick: function() {

                    }
                }
                set.results.push(result);
            });
            return [set];
        }
        return new Promise(function(resolve, reject) {
            frappe.call({
                method: "frappe.utils.global_search.get_forum_results",
                args: {
                    text: keywords
                },
                callback: function(r) {
                    if(r.message) {
                        resolve(get_results_set(r.message));
                    } else {
                        resolve([]);
                    }
                }
            });
        });
    },

    get_nav: function(keywords) {

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
    fuzzy_search: function(keywords, _item, process) {
        // Returns 1 for case-perfect contain, 0 for not found
            // 0.9 for perfect contain,
            // 0 - 0.5 for fuzzy contain

        // **Specific use-case step**
		item = __(_item || '').replace(/-/g, " ");

		var ilen = item.length;
		var tlen = keywords.length;
        var max_skips = 3, max_mismatch_len = 2;

		if (tlen > ilen) {	return 0;  }

		if (item.indexOf(keywords) !== -1) {
			return 1;
		}

		item = item.toLowerCase();
		keywords = keywords.toLowerCase();

		if (item.indexOf(keywords) !== -1) {
			return 0.9;
		}

        var skips = 0, mismatches = 0;
		outer: for (var i = 0, j = 0; i < tlen; i++) {
			if(mismatches !== 0) skips++;
			if(skips > max_skips) return 0;
			mismatches = 0;
			while (j < ilen) {
				if (item.charCodeAt(j++) === keywords.charCodeAt(i)) {
					continue outer;
				}
				mismatches++;
				if(mismatches > max_mismatch_len) { return 0 };
				j++;
			}
			return 0;
		}

        // Since indexOf didn't pass, there will be atleast 1 skip
        // hence no divide by zero
        return 0.5/(skips + mismatches);
	},

    replace_with_bold: function(string, subsequence) {
		var rendered = "";
        if(this.fuzzy_search(subsequence, string) === 0) {
            return string;
        } else if(this.fuzzy_search(subsequence, string) > 0.5) {
            var regEx = new RegExp("("+ subsequence +")", "ig");
            return string.replace(regEx, '<b>$1</b>');
        } else {
            var string_orig = string;
            var string = string.toLowerCase();
            var subsequence = subsequence.toLowerCase();
            outer: for(var i = 0, j = 0; i < subsequence.length; i++) {
                while(j < string.length) {
                    if(string.charCodeAt(j) === subsequence.charCodeAt()) {
                        var string_char =  string_orig.charAt(j);
                        if(string_char === string_char.toLowerCase()) {
                            rendered += '<b>' + subsequence.charAt(i) + '</b>';
                        } else {
                            rendered += '<b>' + subsequence.charAt(i).toUpperCase() + '</b>';
                        }
                        j++;
                        continue outer;
                    }
                    rendered += string_orig.charAt(j);
                }
                return string_orig;
            }
            rendered += string_orig.slice(j);
            return rendered;
        }


    },

    sort_by_rank: function(arr) {
        return arr.sort(function(a, b) {
            return a.index - b.index || a.value.length - b.value.length;
        });
    },

    reverse_scrub: function(str) {
        return __(str || '').replace(/-|_/g, " ").replace(/\w*/g,
            function(txt){return txt.charAt(0).toUpperCase() + txt.substr(1).toLowerCase();});
    },
}