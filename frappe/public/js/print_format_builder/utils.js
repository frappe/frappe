export function create_default_layout(meta, print_format) {
	let layout = {
		header: get_default_header(meta),
		sections: [],
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
			columns: [],
		};
	}

	function get_new_column(df) {
		if (!df) {
			df = { label: "" };
		}
		return {
			label: df.label || "",
			fields: [],
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
					options: df.options,
				};

				let field_template = get_field_template(print_format, df.fieldname);
				if (field_template) {
					field.label = `${__(df.label, null, df.parent)} (${__("Field Template")})`;
					field.fieldtype = "Field Template";
					field.field_template = field_template.name;
					field.fieldname = df.fieldname = "_template";
				}

				if (df.fieldtype === "Table") {
					field.table_columns = get_table_columns(df);
				}

				column.fields.push(field);
				section.has_fields = true;
			}
		}
	}

	// remove empty sections
	layout.sections = layout.sections.filter((section) => section.has_fields);

	return layout;
}

export function get_table_columns(df) {
	let table_columns = [];
	let table_fields = frappe.get_meta(df.options).fields;
	let total_width = 0;
	for (let tf of table_fields) {
		if (
			!["Section Break", "Column Break"].includes(tf.fieldtype) &&
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

function get_field_template(print_format, fieldname) {
	let templates = print_format?.__onload?.print_templates || [];
	for (let template of templates) {
		if (template.field === fieldname) {
			return template;
		}
	}
	return null;
}

function get_default_header(meta) {
	return { columns: [{ label: "", fields: [] }] };
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

export async function render_jinja_html(html, doctype, docname) {
	if (!html) return html;
	if (!html.includes("{{") && !html.includes("{%")) return html;
	if (!doctype || !docname) return html;
	try {
		const r = await frappe.call("frappe.utils.print_format_generator.render_jinja_template", {
			template: html,
			doctype,
			docname,
		});
		return r.message ?? html;
	} catch {
		return html;
	}
}

const SAFE_HTML_TAGS = new Set([
	"a",
	"abbr",
	"b",
	"blockquote",
	"br",
	"caption",
	"cite",
	"code",
	"col",
	"colgroup",
	"dd",
	"del",
	"div",
	"dl",
	"dt",
	"em",
	"figcaption",
	"figure",
	"h1",
	"h2",
	"h3",
	"h4",
	"h5",
	"h6",
	"hr",
	"i",
	"img",
	"ins",
	"kbd",
	"li",
	"mark",
	"ol",
	"p",
	"pre",
	"q",
	"s",
	"samp",
	"small",
	"span",
	"strong",
	"sub",
	"summary",
	"sup",
	"table",
	"tbody",
	"td",
	"tfoot",
	"th",
	"thead",
	"tr",
	"u",
	"ul",
	"var",
	"wbr",
]);

const SAFE_HTML_ATTRS = new Set([
	"alt",
	"cite",
	"class",
	"colspan",
	"datetime",
	"dir",
	"height",
	"href",
	"lang",
	"rowspan",
	"scope",
	"span",
	"src",
	"style",
	"title",
	"width",
	"align",
	"valign",
	"border",
	"cellpadding",
	"cellspacing",
]);

export function sanitize_html(html) {
	const root = document.createElement("div");
	root.innerHTML = frappe.dom.remove_script_and_style(html || "");
	(function clean(node) {
		for (const child of [...node.childNodes]) {
			if (child.nodeType === Node.TEXT_NODE) continue;
			if (child.nodeType !== Node.ELEMENT_NODE) {
				child.remove();
				continue;
			}
			if (!SAFE_HTML_TAGS.has(child.tagName.toLowerCase())) {
				child.replaceWith(...child.childNodes);
				continue;
			}
			for (const attr of [...child.attributes]) {
				const name = attr.name.toLowerCase();
				if (!SAFE_HTML_ATTRS.has(name) || name.startsWith("on")) {
					child.removeAttribute(attr.name);
				} else if (name === "src") {
					if (!/^(https?:|data:image\/)/i.test(attr.value.trim()))
						child.removeAttribute(attr.name);
				} else if (name === "href") {
					if (!/^https?:/i.test(attr.value.trim())) child.removeAttribute(attr.name);
				}
			}
			clean(child);
		}
	})(root);
	return root.innerHTML;
}

export function get_image_dimensions(src) {
	return new Promise((resolve) => {
		let img = new Image();
		img.onload = function () {
			resolve({ width: this.width, height: this.height });
		};
		img.src = src;
	});
}
