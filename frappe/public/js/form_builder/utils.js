import { useStore } from "./store";

export function create_layout(fields) {
	let store = useStore();

	let layout = {
		tabs: [],
	};

	let tab = null,
		section = null,
		column = null;

	function set_tab(df) {
		tab = get_new_tab(df);
		column = null;
		section = null;
		layout.tabs.push(tab);
	}

	function set_section(df) {
		if (!tab) set_tab();

		section = get_new_section(df, tab);
		column = null;
		tab.sections.push(section);
	}

	function set_column(df) {
		if (!section) set_section();

		column = get_new_column(df);
		section.columns.push(column);
	}

	function get_new_tab(df) {
		let _tab = {};
		_tab.df = df || store.get_df("Tab Break", "", __("Details"));
		_tab.sections = [];
		_tab.is_first = !df;
		return _tab;
	}

	function get_new_section(df) {
		let _section = {};
		_section.df = df || store.get_df("Section Break");
		_section.columns = [];
		_section.is_first = !df;
		return _section;
	}

	function get_new_column(df) {
		let _column = {};
		_column.df = df || store.get_df("Column Break");
		_column.fields = [];
		_column.is_first = !df;
		return _column;
	}

	for (let df of fields) {
		if (df.fieldname) {
			// make a copy to avoid mutation bugs
			df = JSON.parse(JSON.stringify(df));
		}

		if (df.fieldtype === "Tab Break") {
			set_tab(df);
		} else if (df.fieldtype === "Section Break") {
			set_section(df);
		} else if (df.fieldtype === "Column Break") {
			set_column(df);
		} else {
			if (!column) set_column();

			let field = { df: df };

			if (df.fieldtype === "Table") {
				field.table_columns = get_table_columns(df);
			}

			column.fields.push(field);
			section.has_fields = true;
		}
	}

	// remove empty sections
	for (let tab of layout.tabs) {
		for (let i = tab.sections.length - 1; i >= 0; --i) {
			let section = tab.sections[i];
			if (!section.has_fields) {
				tab.sections.splice(tab.sections.indexOf(section), 1);
			}
		}
	}

	return layout;
}

export async function load_doctype_model(doctype) {
	await frappe.call("frappe.desk.form.load.getdoctype", { doctype });
}

export async function get_table_columns(df, child_doctype) {
	let table_columns = [];

	if (!frappe.get_meta(df.options)) {
		await load_doctype_model(df.options);
	}
	if (!child_doctype) {
		child_doctype = frappe.get_meta(df.options);
	}

	let table_fields = child_doctype.fields;
	let total_colsize = 1;
	table_columns.push([
		{
			label: __("No.", null, "Title of the 'row number' column"),
		},
		1,
	]);
	for (let tf of table_fields) {
		if (!frappe.model.layout_fields.includes(tf.fieldtype) && tf.in_list_view && tf.label) {
			let colsize;

			if (tf.columns) {
				colsize = tf.columns;
			} else {
				colsize = update_default_colsize(tf);
			}

			if (total_colsize > 11 + colsize) {
				continue;
			} else {
				total_colsize += colsize;
				table_columns.push([
					{
						label: tf.label,
						fieldname: tf.fieldname,
						fieldtype: tf.fieldtype,
					},
					colsize,
				]);
			}
		}
	}

	// adjust by increasing column width
	adjust_column_size(total_colsize, true);

	// adjust by decreasing column width
	adjust_column_size(total_colsize);

	function adjust_column_size(total_colsize, increase) {
		let passes = 0;
		let start_condition = increase ? total_colsize < 11 : total_colsize >= 11;

		while (start_condition && passes < 11) {
			for (var i in table_columns) {
				var _df = table_columns[i][0];
				var colsize = table_columns[i][1];
				if (colsize > 1 && colsize < 11 && frappe.model.is_non_std_field(_df.fieldname)) {
					if (
						passes < 3 &&
						["Int", "Currency", "Float", "Check", "Percent"].indexOf(_df.fieldtype) !==
							-1
					) {
						// don't increase/decrease col size of these fields in first 3 passes
						continue;
					}

					if (increase) {
						table_columns[i][1] += 1;
						total_colsize++;
					} else {
						table_columns[i][1] -= 1;
						total_colsize--;
					}
				}

				if (increase && total_colsize > 9) break;
				if (!increase && total_colsize < 11) break;
			}
			passes++;
		}
	}

	function update_default_colsize(_df) {
		let colsize = 2;
		switch (_df.fieldtype) {
			case "Text":
				break;
			case "Small Text":
				colsize = 3;
				break;
			case "Check":
				colsize = 1;
		}
		return colsize;
	}
	return table_columns;
}

export function evaluate_depends_on_value(expression, doc) {
	let store = useStore();
	if (!doc) return;

	let out = null;
	let parent = store.doc;

	if (typeof expression === "boolean") {
		out = expression;
	} else if (typeof expression === "function") {
		out = expression(doc);
	} else if (expression.substr(0, 5) == "eval:") {
		try {
			out = frappe.utils.eval(expression.substr(5), { doc, parent });
			if (parent && parent.istable && expression.includes("is_submittable")) {
				out = true;
			}
		} catch (e) {
			frappe.throw(__('Invalid "depends_on" expression'));
		}
	} else {
		var value = doc[expression];
		if ($.isArray(value)) {
			out = !!value.length;
		} else {
			out = !!value;
		}
	}

	return out;
}

export function section_boilerplate() {
	let store = useStore();

	return {
		df: store.get_df("Section Break"),
		columns: [
			{
				df: store.get_df("Column Break"),
				fields: [],
			},
		],
	};
}

export function move_children_to_parent(props, parent, child, current_container) {
	let store = useStore();

	let children = props[parent][child + "s"];
	let index = children.indexOf(props[child]);

	if (index > 0) {
		const name = parent.charAt(0).toUpperCase() + parent.slice(1);
		// move current children and children after that to a new column
		let new_parent = {
			df: store.get_df(name + " Break"),
			[child + "s"]: children.splice(index),
		};

		// add new parent after current parent
		let parents = current_container[parent + "s"];
		let parent_index = parents.indexOf(props[parent]);
		parents.splice(parent_index + 1, 0, new_parent);

		// remove current child and after that
		children.splice(index + 1);

		return new_parent.df.name;
	}
}

export function scrub_field_names(fields) {
	fields.forEach((d) => {
		if (d.fieldtype) {
			if (!d.fieldname) {
				if (d.label) {
					d.fieldname = d.label.trim().toLowerCase().replaceAll(" ", "_");
					if (d.fieldname.endsWith("?")) {
						d.fieldname = d.fieldname.slice(0, -1);
					}
					if (frappe.model.restricted_fields.includes(d.fieldname)) {
						d.fieldname = d.fieldname + "1";
					}
					if (d.fieldtype == "Section Break") {
						d.fieldname = d.fieldname + "_section";
					} else if (d.fieldtype == "Column Break") {
						d.fieldname = d.fieldname + "_column";
					} else if (d.fieldtype == "Tab Break") {
						d.fieldname = d.fieldname + "_tab";
					}
				} else {
					d.fieldname =
						d.fieldtype.toLowerCase().replaceAll(" ", "_") +
						"_" +
						frappe.utils.get_random(4);
				}
			} else {
				if (frappe.model.restricted_fields.includes(d.fieldname)) {
					frappe.throw(__("Fieldname {0} is restricted", [d.fieldname]));
				}
			}
			let regex = new RegExp(/['",./%@()<>{}]/g);
			d.fieldname = d.fieldname.replace(regex, "");
			// fieldnames should be lowercase
			d.fieldname = d.fieldname.toLowerCase();
		}

		// unique is automatically an index
		if (d.unique) {
			d.search_index = 0;
		}
	});

	return fields;
}

export function clone_field(field) {
	let cloned_field = JSON.parse(JSON.stringify(field));
	cloned_field.df.name = frappe.utils.get_random(8);
	return cloned_field;
}

export function confirm_dialog(
	title,
	message,
	primary_action,
	primary_action_label,
	secondary_action,
	secondary_action_label
) {
	let d = new frappe.ui.Dialog({
		title: title,
		primary_action_label: primary_action_label || __("Yes"),
		primary_action: () => {
			primary_action && primary_action();
			d.hide();
		},
		secondary_action_label: secondary_action_label || __("No"),
		secondary_action: () => {
			secondary_action && secondary_action();
			d.hide();
		},
	});
	d.show();
	d.set_message(message);
}

export function is_touch_screen_device() {
	return "ontouchstart" in document.documentElement;
}
