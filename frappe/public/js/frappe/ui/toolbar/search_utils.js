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
					label: __("{0}" , [__(me.bolden_match_part(item, keywords))]),
					value: item,
					index: level,
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
					label: __("{0}", [__(me.bolden_match_part(item, keywords))]),
					value: item,
					index: level,
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
        var me = this;
        function get_results_sets(data) {
            var results_sets = [], result, set;
            var get_existing_set = function(doctype) {
                return results_sets.find(function(set) {
                    return set.title === doctype;
                });
            }
            data.forEach(function(d) {
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
                        results: [result],
                        fetch_type: "Global"
                    }
                    results_sets.push(set);
                }

            });
            return results_sets;
        }
        return new Promise(function(resolve, reject) {
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

    get_results_from_doctype: function(doctype, keywords, start, limit, callback) {
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
                    results = [];
                    r.message.forEach(function(d) {
                        results.push({
                            label: d.name,
                            value: d.name,
                            description: d.content,
                            route: ['Form', doctype, d.name]
                        });
                    });
                    callback(doctype, results, limit);
                } else {
                    callback(doctype, [], limit);
                }
            }
        });
    },

    get_help_results: function(keywords) {
        function get_results_set(data) {
            var result;
            var set = {
                title: "Help",
                fetch_type: "Help",
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

    get_nav_results: function(keywords) {
        var compare = function(a, b) {
			return a.index - b.index || a.value.length - b.value.length;
		}
		// var all_doctypes = this.get_doctypes(keywords);
		// all_doctypes.forEach(function(d) {
		// 	if(d.type === "") {
		// 		setup.push(d);
		// 	} else {
		// 		lists.push(d);
		// 	}
		// });
		return [
			// "Lists": lists.sort(compare),
			{title: "Reports", fetch_type: "Nav", results: this.get_reports(keywords).sort(compare)},
			{title: "Modules", fetch_type: "Nav", results: this.get_modules(keywords).sort(compare)},
			// "Administration": this.get_pages(keywords).sort(compare),
			// "Setup": setup.sort(compare)
        ]
    },

    get_recent_pages: function(keywords) {

    },
    // Find stuff given a condition
    parse_keyword_and_trigger_results: function(input) {

    },

    // Utils
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

    replace_with_bold: function(str, subseq) {
		var rendered = "";
        if(this.fuzzy_search(subseq, str) === 0) {
            return str;
        } else if(this.fuzzy_search(subseq, str) > 0.5) {
            var regEx = new RegExp("("+ subseq +")", "ig");
            return str.replace(regEx, '<b>$1</b>');
        } else {
            var str_orig = str;
            var str = str.toLowerCase();
            var subseq = subseq.toLowerCase();
            outer: for(var i = 0, j = 0; i < subseq.length; i++) {
                while(j < str.length) {
                    if(str.charCodeAt(j) === subseq.charCodeAt()) {
                        var str_char =  str_orig.charAt(j);
                        if(str_char === str_char.toLowerCase()) {
                            rendered += '<b>' + subseq.charAt(i) + '</b>';
                        } else {
                            rendered += '<b>' + subseq.charAt(i).toUpperCase() + '</b>';
                        }
                        j++;
                        continue outer;
                    }
                    rendered += str_orig.charAt(j);
                }
                return str_orig;
            }
            rendered += str_orig.slice(j);
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