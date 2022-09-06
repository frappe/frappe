export function create_layout(fields) {
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

	function set_column(df) {
		if (!section) {
			set_section();
		}
		column = get_new_column(df);
		section.columns.push(column);
	}

	function set_section(df) {
		if (!tab) {
			set_tab();
		}
		section = get_new_section(df, tab);
		column = null;
		tab.sections.push(section);
	}

	function get_new_tab(df) {
		let field = {};
		if (!df) {
			df = {
				label: __("Details"),
				fieldtype: "Tab Break",
			};
			field.new_field = true;
		}
		field.df = df;
		field.sections = [];
		return field;
	}

	function get_new_section(df) {
		let field = {};
		if (!df) {
			df = { fieldtype: "Section Break" };
			field.new_field = true;
		}
		field.df = df;
		field.columns = [];
		return field;
	}

	function get_new_column(df) {
		let field = {};
		if (!df) {
			df = { fieldtype: "Column Break" };
			field.new_field = true;
		}
		field.df = df;
		field.fields = [];
		return field;
	}

	for (let df of fields) {
		if (df.fieldname) {
			// make a copy to avoid mutation bugs
			df = JSON.parse(JSON.stringify(df));
		} else {
			continue;
		}

		if (df.fieldtype === "Tab Break") {
			set_tab(df);
		} else if (df.fieldtype === "Section Break") {
			set_section(df);
		} else if (df.fieldtype === "Column Break") {
			set_column(df);
		} else if (df.name) {
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
		for (let section of tab.sections) {
			if (!section.has_fields) {
				tab.sections.splice(tab.sections.indexOf(section), 1);
			}
		}
	}

	return layout;
}

export function get_table_columns(df) {
	let table_columns = [];
	let table_fields = frappe.get_meta(df.options).fields;
	let total_width = 0;
	for (let tf of table_fields) {
		if (
			!in_list(["Tab Break", "Section Break", "Column Break", "Fold"], tf.fieldtype) &&
			!tf.print_hide &&
			df.label &&
			total_width < 100
		) {
			let width =
				typeof tf.width == "number" && tf.width < 100 ? tf.width : tf.width ? 20 : 10;
			table_columns.push({
				label: tf.label,
				fieldname: tf.fieldname,
				fieldtype: tf.fieldtype,
				options: tf.options,
				width,
			});
			total_width += width;
		}
	}
	return table_columns;
}

export function evaluate_depends_on_value(expression, doc) {
	if (!doc) return;

	let out = null;
	let parent = doc || null;

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
