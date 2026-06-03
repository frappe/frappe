frappe.provide("frappe.search");
import { fuzzy_match } from "./fuzzy_match.js";

frappe.search.utils = {
	setup_recent: function () {
		this.recent = JSON.parse(frappe.boot.user.recent || "[]") || [];
	},
	results_to_hide: [],
	get_recent_pages: function (keywords) {
		if (keywords === null) keywords = "";
		var me = this,
			values = [],
			options = [];

		function find(list, keywords, process) {
			list.forEach(function (item, i) {
				var _item = $.isArray(item) ? item[0] : item;
				_item = __(_item || "")
					.toLowerCase()
					.replace(/-/g, " ");

				if (keywords === _item || _item.indexOf(keywords) !== -1) {
					var option = process(item);

					if (option) {
						if ($.isPlainObject(option)) {
							option = [option];
						}
						option.forEach(function (o) {
							o.match = item;
							o.recent = true;
						});

						options = option.concat(options);
					}
				}
			});
		}

		me.recent.forEach(function (doctype, i) {
			values.push([doctype[1], ["Form", doctype[0], doctype[1]]]);
		});

		values = values.reverse();

		frappe.route_history.forEach(function (route, i) {
			if (route[0] === "Form") {
				values.push([route[2], route]);
			} else if (
				["List", "Tree", "Workspaces", "query-report"].includes(route[0]) ||
				route[2] === "Report"
			) {
				if (route[1]) {
					values.push([route[1], route]);
				}
			} else if (route[0]) {
				values.push([frappe.route_titles[route.join("/")] || route[0], route]);
			}
		});

		find(values, keywords, function (match) {
			const route = match[1];
			const out = { route: route };

			if (route[0] === "Form") {
				const doctype = route[1];
				if (route.length > 2 && doctype !== route[2]) {
					const docname = route[2];
					out.label = __(doctype) + " " + docname.bold();
					out.value = __(doctype) + " " + docname;
				} else {
					out.label = __(doctype).bold();
					out.value = __(doctype);
				}
			} else if (
				["List", "Tree", "Workspaces", "query-report"].includes(route[0]) &&
				route.length > 1
			) {
				const view_type = route[0];
				const view_name = route[1];

				let labelSuffix;

				switch (view_type) {
					case "List":
						labelSuffix = __("List");
						break;
					case "Tree":
						labelSuffix = __("Tree");
						break;
					case "Workspaces":
						labelSuffix = __("Workspace");
						break;
					case "query-report":
						labelSuffix = __("Report");
						break;
				}

				out.label = __(view_name.bold()) + " " + labelSuffix;
				out.value = __(view_name) + " " + labelSuffix;
			} else if (match[0]) {
				out.label = frappe.utils.escape_html(match[0]).bold();
				out.value = match[0];
			} else {
				console.log("Illegal match", match);
			}
			out.index = 80;
			return out;
		});
		this.hide_results(options);
		return options;
	},
	hide_results(options) {
		if (this.results_to_hide.length == 0) return;
		this.results_to_hide.forEach((v, i) => {
			options.forEach((o, j) => {
				if (o.value == v) {
					options.splice(j, 1);
				}
			});
		});
	},
	get_frequent_links() {
		let options = [];
		frappe.boot.frequently_visited_links.forEach((link) => {
			const label = frappe.utils.get_route_label(link.route);
			options.push({
				route: link.route,
				label: label,
				value: label,
				index: link.count,
			});
		});
		if (!options.length) {
			return this.get_recent_pages("");
		}
		return options;
	},

	get_search_in_list: function (keywords) {
		var me = this;
		var out = [];
		if (keywords.split(" ").includes("in") && keywords.slice(-2) !== "in") {
			var parts = keywords.split(" in ");
			frappe.boot.user.can_read.forEach(function (item) {
				if (frappe.boot.user.can_search.includes(item)) {
					const search_result = me.fuzzy_search(parts[1], item, true);
					if (search_result.score) {
						out.push({
							type: "In List",
							label: __("Find {0} in {1}", [
								__(parts[0]),
								search_result.marked_string,
							]),
							value: __("Find {0} in {1}", [__(parts[0]), __(item)]),
							route_options: { name: ["like", "%" + parts[0] + "%"] },
							index: 1 + search_result.score,
							route: ["List", item],
						});
					}
				}
			});
		}
		return out;
	},

	get_creatables: function (keywords) {
		var me = this;
		var out = [];
		var firstKeyword = keywords.split(" ")[0];
		if (firstKeyword.toLowerCase() === __("new")) {
			frappe.boot.user.can_create.forEach(function (item) {
				const search_result = me.fuzzy_search(keywords.substr(4), item, true);
				var level = search_result.score;
				if (level) {
					out.push({
						type: "New",
						label: __("New {0}", [search_result.marked_string || __(item)]),
						value: __("New {0}", [__(item)]),
						index: 1 + level,
						match: item,
						onclick: function () {
							frappe.new_doc(item, true);
						},
					});
				}
			});
		}
		return out;
	},

	get_doctypes: function (keywords) {
		var me = this;
		var out = [];

		var score, marked_string, target;
		var option = function (type, route, order) {
			// check to skip extra list in the text
			// eg. Price List List should be only Price List
			let skip_list = type === "List" && target.endsWith("List");
			if (skip_list) {
				var label = marked_string || __(target);
			} else {
				label = __(`{0} ${skip_list ? "" : type}`, [marked_string || __(target)]);
			}
			return {
				type: type,
				label: label,
				value: __(`{0} ${type}`, [target]),
				index: score + order,
				match: target,
				route: route,
			};
		};
		frappe.boot.user.can_read.forEach(function (item) {
			const search_result = me.fuzzy_search(keywords, item, true);
			({ score, marked_string } = search_result);
			if (score) {
				target = item;
				if (frappe.boot.single_types.includes(item)) {
					out.push(option("", ["Form", item, item], 0.05));
				} else if (frappe.boot.user.can_search.includes(item)) {
					// include 'making new' option
					if (frappe.boot.user.can_create.includes(item)) {
						var match = item;
						out.push({
							type: "New",
							label: __("New {0}", [search_result.marked_string || __(item)]),
							value: __("New {0}", [__(item)]),
							index: score + 0.015,
							match: item,
							onclick: function () {
								frappe.new_doc(match, true);
							},
						});
					}
					const isTree = (frappe.boot.tree_view_doctypes || []).includes(item);
					let option_data = option(
						isTree ? "Tree" : "List",
						isTree ? ["Tree", item] : ["List", item],
						0.05
					);
					let sidebars = frappe.app.sidebar.get_workspace_sidebars(item);
					if (sidebars.length > 1) {
						sidebars.forEach((sidebar) => {
							let sidebar_option = option(
								isTree ? "Tree" : "List",
								isTree ? ["Tree", item] : ["List", item],
								0.05
							);
							sidebar_option.description = `${sidebar}`;
							sidebar_option.type = "sidebar";
							out.push(sidebar_option);
						});
					} else {
						out.push(option_data);
					}
					if (frappe.model.can_get_report(item)) {
						out.push(option("Report", ["List", item, "Report"], 0.04));
					}
				}
			}
		});
		return out;
	},

	get_reports: function (keywords) {
		var me = this;
		var out = [];
		var route;
		Object.keys(frappe.boot.user.all_reports).forEach(function (item) {
			const search_result = me.fuzzy_search(keywords, item, true);
			var level = search_result.score;
			if (level > 0) {
				var report = frappe.boot.user.all_reports[item];
				if (report.report_type == "Report Builder")
					route = ["List", report.ref_doctype, "Report", item];
				else route = ["query-report", item];
				out.push({
					type: "Report",
					label: __("Report {0}", [search_result.marked_string || __(item)]),
					value: __("Report {0}", [__(item)]),
					index: level,
					route: route,
				});
			}
		});
		return out;
	},

	get_pages: function (keywords) {
		var me = this;
		var out = [];
		this.pages = {};
		$.each(frappe.boot.page_info, function (name, p) {
			me.pages[p.title] = p;
			p.name = name;
		});
		Object.keys(this.pages).forEach(function (item) {
			if (item == "Hub" || item == "hub") return;
			const search_result = me.fuzzy_search(keywords, item, true);
			var level = search_result.score;
			if (level) {
				var page = me.pages[item];
				out.push({
					type: "Page",
					label: __("Open {0}", [search_result.marked_string || __(item)]),
					value: __("Open {0}", [__(item)]),
					match: item,
					index: level,
					route: [page.route || page.name],
				});
			}
		});
		var target = "Calendar";
		if (__("calendar").indexOf(keywords.toLowerCase()) === 0) {
			out.push({
				type: "Calendar",
				label: __("Open {0}", [__(target)]),
				value: __("Open {0}", [__(target)]),
				index: me.fuzzy_search(keywords, "Calendar"),
				match: target,
				route: ["List", "Event", target],
			});
		}
		target = "Hub";
		if (__("hub").indexOf(keywords.toLowerCase()) === 0) {
			out.push({
				type: "Hub",
				label: __("Open {0}", [__(target)]),
				value: __("Open {0}", [__(target)]),
				index: me.fuzzy_search(keywords, "Hub"),
				match: target,
				route: [target, "Item"],
			});
		}
		if (__("email inbox").indexOf(keywords.toLowerCase()) === 0) {
			out.push({
				type: "Inbox",
				label: __("Open {0}", [__("Email Inbox")]),
				value: __("Open {0}", [__("Email Inbox")]),
				index: me.fuzzy_search(keywords, "email inbox"),
				match: target,
				route: ["List", "Communication", "Inbox"],
			});
		}
		return out;
	},

	get_desktop_icons: function (keywords) {
		var me = this;
		var out = [];
		frappe.boot.desktop_icons.forEach(function (item) {
			const search_result = me.fuzzy_search(keywords, item.label, true);
			var level = search_result.score;
			if (level > 0) {
				var ret = {
					type: "Desktop Icon",
					label: __("Open {0}", [search_result.marked_string || __(item.label)]),
					value: __("Open {0}", [__(item.label)]),
					index: level,
					icon_data: item,
				};

				out.push(ret);
			}
		});
		return out;
	},

	get_dashboards: function (keywords) {
		var me = this;
		var out = [];
		frappe.boot.dashboards.forEach(function (item) {
			const search_result = me.fuzzy_search(keywords, item.name, true);
			var level = search_result.score;
			if (level > 0) {
				var ret = {
					type: "Dashboard",
					label: __("{0} Dashboard", [search_result.marked_string || __(item.name)]),
					value: __("{0} Dashboard", [__(item.name)]),
					index: level,
					route: ["dashboard-view", item.name],
				};

				out.push(ret);
			}
		});
		return out;
	},

	get_global_results: function (keywords, start, limit, doctype = "") {
		var me = this;
		function get_results_sets(data) {
			var results_sets = [],
				result,
				set;
			function get_existing_set(doctype) {
				return results_sets.find(function (set) {
					return set.title === doctype;
				});
			}

			function make_description(content, doc_name) {
				var parts = content.split(" ||| ");
				var result_max_length = 300;
				var field_length = 120;
				var fields = [];
				var result_current_length = 0;
				var field_text = "";
				for (var i = 0; i < parts.length; i++) {
					var part = parts[i];
					if (part.toLowerCase().indexOf(keywords.toLowerCase()) !== -1) {
						// If the field contains the keyword
						let colon_index, field_value;
						if (part.indexOf(" &&& ") !== -1) {
							colon_index = part.indexOf(" &&& ");
							field_value = part.slice(colon_index + 5);
						} else {
							colon_index = part.indexOf(" : ");
							field_value = part.slice(colon_index + 3);
						}
						if (field_value.length > field_length) {
							// If field value exceeds field_length, find the keyword in it
							// and trim field value by half the field_length at both sides
							// ellipsify if necessary
							var field_data = "";
							var index = field_value.indexOf(keywords);
							field_data +=
								index < field_length / 2
									? field_value.slice(0, index)
									: "..." + field_value.slice(index - field_length / 2, index);
							field_data += field_value.slice(index, index + field_length / 2);
							field_data +=
								index + field_length / 2 < field_value.length ? "..." : "";
							field_value = field_data;
						}
						var field_name = part.slice(0, colon_index);

						// Find remaining result_length and add field length to result_current_length
						var remaining_length = result_max_length - result_current_length;
						result_current_length += field_name.length + field_value.length + 2;
						const search_result_name = me.fuzzy_search(keywords, field_name, true);
						const search_result_value = me.fuzzy_search(keywords, field_value, true);
						if (result_current_length < result_max_length) {
							// We have room, push the entire field
							field_text =
								'<span class="field-name text-muted">' +
								search_result_name.marked_string +
								": </span> " +
								search_result_value.marked_string;
							if (fields.indexOf(field_text) === -1 && doc_name !== field_value) {
								fields.push(field_text);
							}
						} else {
							// Not enough room
							if (field_name.length < remaining_length) {
								// Ellipsify (trim at word end) and push
								remaining_length -= field_name.length;
								field_text =
									'<span class="field-name text-muted">' +
									search_result_name.marked_string +
									": </span> ";
								field_value = field_value.slice(0, remaining_length);
								field_value =
									field_value.slice(0, field_value.lastIndexOf(" ")) + " ...";
								field_text += search_result_value.marked_string;
								fields.push(field_text);
							} else {
								// No room for even the field name, skip
								fields.push("...");
							}
							break;
						}
					}
				}
				return fields.join(", ");
			}

			data.forEach(function (d) {
				// more properties
				result = {
					label: d.title || d.name, // show title if exists
					value: d.name,
					description: make_description(d.content, d.name),
					route: ["Form", d.doctype, d.name],
					_global_raw_content: d.content,
					_global_doctype: d.doctype,
				};
				if (d.image || d.image === null) {
					result.image = d.image;
				}
				set = get_existing_set(d.doctype);
				if (set) {
					set.results.push(result);
				} else {
					set = {
						title: d.doctype,
						results: [result],
						fetch_type: "Global",
					};
					results_sets.push(set);
				}
			});
			return results_sets;
		}
		return new Promise(function (resolve, reject) {
			var args = { text: keywords };
			if (doctype) {
				args.doctype = doctype;
			}
			var offset = parseInt(start, 10) || 0;
			if (offset > 0) {
				args.start = offset;
				args.limit = parseInt(limit, 10);
				if (!args.limit || args.limit < 1) {
					args.limit = 20;
				}
			}
			frappe.call({
				method: "frappe.utils.global_search.search",
				args: args,
				callback: function (r) {
					if (r.message) {
						resolve(get_results_sets(r.message));
					} else {
						resolve([]);
					}
				},
			});
		});
	},

	/**
	 * Parses `__global_search` content into { field label - value list }.
	 * Segments are separated by `|||`; each segment is `label : value` (or `label &&& value` as fallback).
	 * Skips blank parts and the synthetic `name` field (the real name is shown in its own column).
	 */
	parse_global_search_fields: function (content) {
		const fields = {};
		if (!content) return fields;
		for (const raw of content.split("|||")) {
			let part = (raw || "").trim();
			if (!part.length) continue;
			let sep = " : ";
			let idx = part.indexOf(sep);
			if (idx === -1) {
				sep = " &&& ";
				idx = part.indexOf(sep);
			}
			if (idx === -1) continue;
			const label = part.slice(0, idx).trim();
			const value = part.slice(idx + sep.length).trim();
			if (!label.length || /^name$/i.test(label)) continue;
			if (!fields[label]) fields[label] = [];
			fields[label].push(value);
		}
		return fields;
	},

	/**
	 * Picks table column names for Global Search hits: walks each hit’s snippet text,
	 * finds every field label in that text, then returns each label once (first time we see it).
	 */
	global_search_field_columns_for_results: function (results) {
		const cols = [];
		const seen = Object.create(null);
		for (const r of results || []) {
			const fields = this.parse_global_search_fields(r._global_raw_content);
			for (const col of Object.keys(fields)) {
				if (!seen[col]) {
					seen[col] = 1;
					cols.push(col);
				}
			}
		}
		return cols;
	},

	/**
	 * Highlights search terms in text: wraps each term in `<mark>` tags.
	 */
	highlight_global_search_terms: function (text, keywords) {
		const s = text == null ? "" : String(text);
		const terms = keywords
			.split("&")
			.map((p) => p.trim())
			.filter(Boolean);
		if (!terms.length) return frappe.utils.escape_html(s);
		const escaped = terms.map((p) => p.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
		try {
			const re = new RegExp("(" + escaped.join("|") + ")", "gi");
			return s
				.split(re)
				.map((part) => {
					const isMatch =
						part && terms.some((t) => part.toLowerCase() === t.toLowerCase());
					const esc = frappe.utils.escape_html(part);
					return isMatch ? "<mark>" + esc + "</mark>" : esc;
				})
				.join("");
		} catch (e) {
			return frappe.utils.escape_html(s);
		}
	},

	fuzzy_search: function (keywords = "", _item = "", return_marked_string = false) {
		let item = __(_item);

		let [, score, matches] = fuzzy_match(keywords, item, return_marked_string);
		if (score == 0 && frappe.boot.lang !== "en" && item != _item) {
			item = _item || "";
			[, score, matches] = fuzzy_match(keywords, item, return_marked_string);
		}

		if (!return_marked_string) {
			return score;
		}
		if (score == 0) {
			return {
				score: score,
				marked_string: item,
			};
		}

		// Create Boolean mask to mark matching indices in the item string
		const matchArray = Array(item.length).fill(0);
		matches.forEach((index) => (matchArray[index] = 1));

		let marked_string = "";
		let buffer = "";

		// Clear the buffer and return marked matches.
		const flushBuffer = () => {
			if (!buffer) return "";
			const temp = `<mark>${buffer}</mark>`;
			buffer = "";
			return temp;
		};

		matchArray.forEach((isMatch, index) => {
			if (isMatch) {
				buffer += item[index];
			} else {
				marked_string += flushBuffer();
				marked_string += item[index];
			}
		});
		marked_string += flushBuffer();

		return { score, marked_string };
	},

	/**
	 * @deprecated Use frappe.search.utils.fuzzy_search(subseq, str, true).marked_string instead.
	 */
	bolden_match_part: function (str, subseq) {
		return this.fuzzy_search(subseq, str, true).marked_string;
	},

	get_executables(keywords) {
		let results = [];
		this.searchable_functions.forEach((item) => {
			const target = item.label.toLowerCase();
			const txt = keywords.toLowerCase();
			if (txt === target || target.indexOf(txt) === 0) {
				const search_result = this.fuzzy_search(txt, item.label, true);
				results.push({
					type: "Executable",
					value: search_result.marked_string,
					index: search_result.score,
					match: item.label,
					onclick: () => item.action.apply(this, item.args),
				});
			}
		});
		return results;
	},
	make_function_searchable(_function, label = null, args = null) {
		if (typeof _function !== "function") {
			throw new Error("First argument should be a function");
		}

		this.searchable_functions.push({
			label: label || _function.name,
			action: _function,
			args: args,
		});
	},
	get_marketplace_apps: function (keywords) {
		var me = this;
		var out = [];
		frappe.boot.marketplace_apps.forEach(function (item) {
			const search_result = me.fuzzy_search(keywords, item.title, true);
			if (search_result.score > 0) {
				var ret = {
					label: __("Install {0} from Marketplace", [search_result.marked_string]),
					value: __("Install {0} from Marketplace", [__(item.title)]),
					index: search_result.score * 0.8,
					route: [
						`https://frappecloud.com/${item.route}?utm_source=awesomebar`,
						item.name,
					],
				};

				out.push(ret);
			}
		});
		return out;
	},
	searchable_functions: [],
};

/** Closes the navbar Awesome Bar modal. */
function hide_navbar_search_modal() {
	const $modal = $("#navbar-search").closest(".modal");
	if ($modal.length) $modal.modal("hide");
}

/**
 * Open the global search dialog from the navbar Awesome Bar (Ctrl/Cmd+G).
 */
frappe.search.open_global_search_from_navbar_shortcut = function (e) {
	const from_bar = ($("#navbar-search").val() || "").trim();
	const dlg = frappe.searchdialog?.search;
	if (dlg?.open_global_search_dialog) {
		hide_navbar_search_modal();
		dlg.open_global_search_dialog(from_bar);
	}
	if (e) {
		e.preventDefault();
	}
	return false;
};

/**
 * Open the navbar Awesome Bar from Global Search (Ctrl/Cmd+K).
 */
frappe.search.open_awesomebar_from_global_search_shortcut = function (e) {
	if (e) {
		e.preventDefault();
	}
	const awesome_bar = frappe.app.awesome_bar;
	if (awesome_bar?.is_open()) {
		awesome_bar.close();
		return false;
	}
	const dlg = frappe.searchdialog?.search;
	if (dlg?.search_dialog?.is_visible) {
		const keywords = (dlg.$input?.val() || "").trim();
		dlg.search_dialog.hide();
		$("#navbar-search").val(keywords);
	}
	awesome_bar.open();
	return false;
};
