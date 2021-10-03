export function create_default_layout(meta) {
	let layout = {
		sections: []
	};

	let section = null,
		column = null;

	function set_column(df) {
		if (!section) {
			set_section();
		}
		column = get_new_column(df);
		section.columns.push(column);
	}

	function set_section(df) {
		section = get_new_section(df);
		column = null;
		layout.sections.push(section);
	}

	function get_new_section(df) {
		if (!df) {
			df = { label: "" };
		}
		return {
			label: df.label || "",
			columns: []
		};
	}

	function get_new_column(df) {
		if (!df) {
			df = { label: "" };
		}
		return {
			label: df.label || "",
			fields: []
		};
	}

	for (let df of meta.fields) {
		if (df.fieldname) {
			// make a copy to avoid mutation bugs
			df = JSON.parse(JSON.stringify(df));
		} else {
			continue;
		}

		if (df.fieldtype === "Section Break") {
			set_section(df);
		} else if (df.fieldtype === "Column Break") {
			set_column(df);
		} else if (df.label) {
			if (!column) set_column();

			if (!df.print_hide) {
				let field = {
					label: df.label,
					fieldname: df.fieldname,
					fieldtype: df.fieldtype,
					options: df.options
				};

				if (df.fieldtype === "Table") {
					field.table_columns = get_table_columns(df);
				}

				column.fields.push(field);
				section.has_fields = true;
			}
		}
	}

	// remove empty sections
	layout.sections = layout.sections.filter(section => section.has_fields);

	return layout;
}

export function get_table_columns(df) {
	let table_columns = [];
	let table_fields = frappe.get_meta(df.options).fields;
	let total_width = 0;
	for (let tf of table_fields) {
		if (
			!in_list(["Section Break", "Column Break"], tf.fieldtype) &&
			!tf.print_hide &&
			df.label &&
			total_width < 100
		) {
			let width =
				typeof tf.width == "number" && tf.width < 100
					? tf.width
					: tf.width
					? 20
					: 10;
			table_columns.push({
				label: tf.label,
				fieldname: tf.fieldname,
				fieldtype: tf.fieldtype,
				options: tf.options,
				width
			});
			total_width += width;
		}
	}
	return table_columns;
}

export function pluck(object, keys) {
	let out = {};
	for (let key of keys) {
		if (key in object) {
			out[key] = object[key];
		}
	}
	return out;
}

export function get_image_dimensions(src) {
	return new Promise(resolve => {
		let img = new Image();
		img.onload = function() {
			resolve({ width: this.width, height: this.height });
		};
		img.src = src;
	});
}
