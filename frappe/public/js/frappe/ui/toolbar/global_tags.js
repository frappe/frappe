// Copyright (c) 2019, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.provide("frappe.global_tags");

frappe.global_tags.utils = {
	get_tags: function(txt) {
		txt = txt.slice(1);
		let out = [];

		for (let i in frappe.global_tags.tags) {
			let tag = frappe.global_tags.tags[i];
			let level = frappe.search.utils.fuzzy_search(txt, tag);
			if (level) {
				out.push({
					type: "Tag",
					label: __("#{0}", [frappe.search.utils.bolden_match_part(__(tag), txt)]),
					value: __("#{0}", [__(tag)]),
					index: 1 + level,
					match: tag,
					onclick() {
						// Use Global Search Dialog for tag search too.
						frappe.searchdialog.search.init_search("#".concat(tag), "global_tag")
					}
				});
			}
		}

		return out;
	},

	set_tags() {
		frappe.call({
			method: "frappe.utils.global_tags.get_tags_list_for_awesomebar",
			callback: function(r) {
				if (r && r.message) {
					frappe.global_tags.tags = $.extend([], r.message);
				}
			}
		});
	},

	get_tag_results: function(tag) {
		var me = this;
		function get_results_sets(data) {
			var results_sets = [], result, set;
			function get_existing_set(doctype) {
				return results_sets.find(function(set) {
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
				for(var i = 0; i < parts.length; i++) {
					var part = parts[i];
					if(part.toLowerCase().indexOf(tag) !== -1) {
						// If the field contains the keyword
						if(part.indexOf(' &&& ') !== -1) {
							var colon_index = part.indexOf(' &&& ');
							var field_value = part.slice(colon_index + 5);
						} else {
							var colon_index = part.indexOf(' : ');
							var field_value = part.slice(colon_index + 3);
						}
						if(field_value.length > field_length) {
							// If field value exceeds field_length, find the keyword in it
							// and trim field value by half the field_length at both sides
							// ellipsify if necessary
							var field_data = "";
							var index = field_value.indexOf(tag);
							field_data += index < field_length/2 ? field_value.slice(0, index)
								: '...' + field_value.slice(index - field_length/2, index);
							field_data += field_value.slice(index, index + field_length/2);
							field_data += index + field_length/2 < field_value.length ? "..." : "";
							field_value = field_data;
						}
						var field_name = part.slice(0, colon_index);

						// Find remaining result_length and add field length to result_current_length
						var remaining_length = result_max_length - result_current_length;
						result_current_length += field_name.length + field_value.length + 2;
						if(result_current_length < result_max_length) {
							// We have room, push the entire field
							field_text = '<span class="field-name text-muted">' +
								me.bolden_match_part(field_name, tag) + ': </span> ' +
								me.bolden_match_part(field_value, tag);
							if(fields.indexOf(field_text) === -1 && doc_name !== field_value) {
								fields.push(field_text);
							}
						} else {
							// Not enough room
							if(field_name.length < remaining_length){
								// Ellipsify (trim at word end) and push
								remaining_length -= field_name.length;
								field_text = '<span class="field-name text-muted">' +
									me.bolden_match_part(field_name, tag) + ': </span> ';
								field_value = field_value.slice(0, remaining_length);
								field_value = field_value.slice(0, field_value.lastIndexOf(' ')) + ' ...';
								field_text += me.bolden_match_part(field_value, tag);
								fields.push(field_text);
							} else {
								// No room for even the field name, skip
								fields.push('...');
							}
							break;
						}
					}
				}
				return fields.join(', ');
			}

			data.forEach(function(d) {
				// more properties
				result = {
					label: d.name,
					value: d.name,
					description: make_description(d.content, d.name),
					route: ['Form', d.doctype, d.name],

				};
				set = get_existing_set(d.doctype);
				if(set) {
					set.results.push(result);
				} else {
					set = {
						title: d.doctype,
						results: [result],
						fetch_type: "Global"
					};
					results_sets.push(set);
				}

			});
			return results_sets;
		}
		return new Promise(function(resolve, reject) {
			frappe.call({
				method: "frappe.utils.global_tags.get_documents_for_tag",
				args: {
					tag: tag
				},
				callback: function(r) {
					if(r.message) {
						resolve(get_results_sets(r.message));
					} else {
						resolve([]);
					}
				}
			});
		});
	},
}
