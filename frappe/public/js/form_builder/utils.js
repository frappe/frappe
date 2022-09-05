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
		if (!df) {
			df = {
				fieldname: "first_tab",
				new_field: true,
				idx: 1,
			};
		}
		return {
			name: df.name || "",
			label: df.label || "Tab " + df.idx,
			fieldname: df.fieldname || "",
			fieldtype: "Tab Break",
			new_field: df.new_field || false,
			sections: [],
		};
	}

	function get_new_section(df) {
		if (!df) {
			df = { new_field: true };
		}
		return {
			name: df.name || "",
			label: df.label || "",
			fieldname: df.fieldname || "",
			fieldtype: "Section Break",
			new_field: df.new_field || false,
			columns: [],
		};
	}

	function get_new_column(df) {
		if (!df) {
			df = { new_field: true };
		}
		return {
			name: df.name || "",
			label: df.label || "",
			fieldname: df.fieldname || "",
			fieldtype: "Column Break",
			new_field: df.new_field || false,
			fields: [],
		};
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

			let field = {
				name: df.name,
				label: df.label,
				fieldname: df.fieldname,
				fieldtype: df.fieldtype,
				options: df.options,
				new_field: df.new_field || false,
			};

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
