export function clone_plain(obj) {
	return JSON.parse(JSON.stringify(obj));
}

// stable per-object id used to map a field's DOM node back to its object
// (fields have no persistent id of their own) — e.g. for marquee selection
const _field_uids = new WeakMap();
let _field_uid_seq = 0;
export function field_uid(df) {
	if (!_field_uids.has(df)) _field_uids.set(df, "pfb-f-" + ++_field_uid_seq);
	return _field_uids.get(df);
}

// the canvas is scaled via CSS `zoom`; convert a screen-pixel delta to doc px
export function canvas_zoom(el) {
	const c = el?.closest(".print-format-container");
	return parseFloat(c && getComputedStyle(c).getPropertyValue("--pfb-zoom")) || 1;
}

export function read_json(key, fallback = null) {
	try {
		return JSON.parse(localStorage.getItem(key)) || fallback;
	} catch {
		return fallback;
	}
}

export function write_json(key, value) {
	try {
		localStorage.setItem(key, JSON.stringify(value));
		return true;
	} catch {
		return false;
	}
}

// Mirrors typst_emitter.py: TRANSLATABLE_STYLE_PROPS + typst_blockers — a UX
// hint only; the server list is the authority and refuses at save/render
export const TYPST_STYLE_PROPS = new Set([
	"font-weight",
	"border-top",
	"border-bottom",
	"margin-top",
	"padding-top",
	"padding-bottom",
	"flex-direction",
	"align-items",
	"gap",
]);

// Value grammars for the props above — a recognized prop with a value the
// server cannot translate blocks too, it never silently drops
const TYPST_BORDER_VALUE =
	/^\d+(\.\d+)?px\s+\w+\s+(#([0-9a-fA-F]{3}){1,2}|black|gray|silver|white|navy|blue|aqua|teal|purple|fuchsia|maroon|red|orange|yellow|olive|green|lime)$/;

const TYPST_STYLE_VALUES = {
	"font-weight": /^(bold|600|700|800|900)$/,
	"border-top": TYPST_BORDER_VALUE,
	"border-bottom": TYPST_BORDER_VALUE,
	"margin-top": /^\d+(\.\d+)?(px)?$/,
	"padding-top": /^\d+(\.\d+)?(px)?$/,
	"padding-bottom": /^\d+(\.\d+)?(px)?$/,
	gap: /^\d+(\.\d+)?(px)?$/,
};

export function* layout_nodes(layout) {
	const zones = [layout?.header, layout?.footer, ...(layout?.sections || [])];
	for (const zone of zones) {
		if (!zone || typeof zone !== "object") continue;
		yield zone;
		for (const col of zone.columns || []) {
			for (const df of col?.fields || []) if (df && !df.remove) yield df;
		}
	}
}

// mirrors safe_color / COLOR_PATTERN: Typst emits rgb("#..."), a non-hex value blocks
const TYPST_HEX = /^#([0-9a-fA-F]{3,4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$/;
function non_hex_color(value) {
	return value && !TYPST_HEX.test(String(value).trim());
}

export function typst_blockers_client(print_format, layout, letterhead) {
	const blockers = [];
	const add = (reason) => !blockers.includes(reason) && blockers.push(reason);
	if (print_format?.custom_format) return [__("Custom HTML format")];
	if (!print_format?.print_format_builder_beta) return [__("Not a builder format")];
	if ((print_format?.css || "").trim()) add(__("Custom CSS on the format"));
	for (const key of ["label_color", "value_color"]) {
		if (non_hex_color(print_format?.[key]))
			add(__("Format color Typst can't render: {0}", [print_format[key]]));
	}
	if (letterhead) {
		if ((letterhead.custom_css || "").trim()) add(__("Letterhead with custom CSS"));
		const header_is_image = letterhead.source === "Image" && letterhead.image;
		if ((letterhead.content || "").trim() && !header_is_image)
			add(__("Letterhead with HTML content"));
		const footer_is_image = letterhead.footer_source === "Image" && letterhead.footer_image;
		if ((letterhead.footer || "").trim() && !footer_is_image)
			add(__("Letterhead footer with HTML content"));
	}
	for (const node of layout_nodes(layout)) {
		if ((node.custom_style || "").trim()) {
			const unknown = [];
			for (const declaration of node.custom_style.split(";")) {
				if (!declaration.includes(":")) continue;
				const [raw_prop, raw_value] = declaration.split(/:(.+)/);
				const prop = raw_prop.trim().toLowerCase();
				const value = (raw_value || "").trim();
				if (!prop) continue;
				if (!TYPST_STYLE_PROPS.has(prop)) {
					unknown.push(prop);
				} else if (TYPST_STYLE_VALUES[prop] && !TYPST_STYLE_VALUES[prop].test(value)) {
					unknown.push(`${prop}: ${value}`);
				}
			}
			if (unknown.length) add(__("Untranslatable CSS: {0}", [unknown.join(", ")]));
		}
		if (node.fieldtype === "HTML") add(__("Custom HTML block"));
		if (node.fieldtype === "Field Template") add(__("Field Template (Jinja HTML)"));
		if (node.fieldtype === "Linked Field") add(__("Linked Field"));
		if (node.fieldtype === "Summary Table") add(__("Summary Table"));
		if (node.fieldtype === "Barcode") {
			if (node.custom) {
				if (node.barcode_format !== "QR") add(__("Barcode (non-QR)"));
			} else {
				const meta_df = frappe.meta.get_docfield(print_format?.doc_type, node.fieldname);
				if (!meta_df || !is_qr_barcode_options(meta_df.options))
					add(__("Barcode (non-QR)"));
			}
		}
		if (node.fieldtype === "Image" && /^https?:\/\//.test(node.image_url || ""))
			add(__("Remote image URL"));
		for (const key of ["label_color", "value_color"]) {
			if (non_hex_color(node[key]))
				add(__("Field color Typst can't render: {0}", [node[key]]));
		}
	}
	return blockers;
}

// Blocks the builder invents — they never map to a docfield on the document type
export const BLOCK_FIELDTYPES = new Set(["Spacer", "Divider", "Repeater", "HTML"]);

// Mirrors PrintFormatGenerator.JUSTIFY_MODES; the class names are spelled out so
// both surfaces can be grepped for them
export const JUSTIFY_CLASSES = {
	"space-between": "row-col-space-between",
	"space-evenly": "row-col-space-evenly",
	center: "row-col-center",
	"right-end": "row-col-right-end",
};

// Mirrors print_format_generator.is_qr_barcode_options: a Barcode docfield whose
// options ask for a qr code — "qrcode"/"qr" or JSON like {"format": "qrcode"}
export function is_qr_barcode_options(options) {
	options = (options || "").trim();
	if (["qr", "qrcode"].includes(options.toLowerCase())) return true;
	try {
		return ["qr", "qrcode"].includes((JSON.parse(options).format || "").toLowerCase());
	} catch {
		return false;
	}
}

export function freshen_field(f) {
	delete f.remove;
	if (f.custom && f.fieldname) f.fieldname += "_" + frappe.utils.get_random(8);
	return f;
}

export function create_default_layout(meta, print_format) {
	let layout = {
		header: get_default_header(),
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
			df = clone_plain(df);
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

function get_default_header() {
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

export const DRAG_OPTIONS = {
	forceFallback: true,
	fallbackOnBody: true,
	fallbackTolerance: 4,
	fallbackClass: "pfb-drag-fallback",
	ghostClass: "pfb-drag-ghost",
};

export function setDragging(active) {
	document.body.classList.toggle("pfb-dragging", active);
	if (active) window.getSelection()?.removeAllRanges();
}

const TABLE_COLUMN_PLUCK_KEYS = [
	"label",
	"fieldname",
	"fieldtype",
	"options",
	"width",
	"field_template",
	"merged_fields",
	"merge_direction",
	"image_size",
	"column_condition",
];

export const FIELD_PLUCK_KEYS = [
	"label",
	"fieldname",
	"fieldtype",
	"options",
	"table_columns",
	"table_style",
	"table_bordered",
	"table_header",
	"table_cell_padding",
	"table_radius",
	"table_header_bg",
	"table_border_color",
	"html",
	"typst",
	"field_template",
	"source",
	"repeater_columns",
	"row_condition",
	"show_label",
	"align",
	"allow_page_break",
	"label_justify",
	"label_gap",
	"visible_if",
	"custom_style",
	"value_color",
	"label_color",
	"custom",
	"image_url",
	"width",
	"height",
	"barcode_field",
	"barcode_value",
	"barcode_format",
	"show_text",
	"text",
	"bold",
	"font_size",
	"link_path",
	"show_empty",
	"hide_colon",
	"group_by",
	"columns",
	"show_totals",
	"table_min_height",
];

const ZONE_FIELD_PLUCK_KEYS = FIELD_PLUCK_KEYS.filter(
	(key) => key !== "table_cell_padding" && key !== "table_radius"
);

export function serialize_layout(layout) {
	layout.sections = layout.sections
		.filter((section) => !section.remove)
		.map((section) => {
			section.columns = section.columns.map((column) => {
				column.fields = column.fields
					.filter((df) => !df.remove)
					.map((df) => {
						if (df.table_columns) {
							df.table_columns = df.table_columns.map((tf) => {
								if (Array.isArray(tf.merged_fields) && !tf.merged_fields.length) {
									delete tf.merged_fields;
								}
								return pluck(tf, TABLE_COLUMN_PLUCK_KEYS);
							});
						}
						return pluck(df, FIELD_PLUCK_KEYS);
					});
				return column;
			});
			return section;
		});

	function clean_zone(zone) {
		if (!zone || !zone.columns) return zone;
		zone.columns = zone.columns.map((column) => {
			column.fields = column.fields
				.filter((df) => !df.remove)
				.map((df) => pluck(df, ZONE_FIELD_PLUCK_KEYS));
			return column;
		});
		return zone;
	}
	layout.header = clean_zone(layout.header);
	layout.footer = clean_zone(layout.footer);

	return layout;
}

// Parse "border: 1px solid; padding: 4px" into a Vue style-binding object.
// Splits on the first ":" per declaration so values like url(http://…) survive.
export function parse_inline_style(css) {
	const style = {};
	if (!css || typeof css !== "string") return style;
	for (const decl of css.split(";")) {
		const idx = decl.indexOf(":");
		if (idx === -1) continue;
		const prop = decl.slice(0, idx).trim();
		const value = decl.slice(idx + 1).trim();
		if (prop && value) style[prop] = value;
	}
	return style;
}

// Deterministic pastel colour for a merged-cell initials thumbnail, keyed off
// the first character so the canvas and the PDF (Table.html, same formula)
// always agree — no palette table to keep in sync across the two.
export function thumb_hue(text) {
	const idx = "abcdefghijklmnopqrstuvwxyz0123456789".indexOf(
		String(text || "")
			.trim()
			.charAt(0)
			.toLowerCase()
	);
	return ((idx < 0 ? 0 : idx) * 37) % 360;
}

export async function render_jinja_html(html, doctype, docname) {
	if (!html) return html;
	if (!html.includes("{{") && !html.includes("{%")) return html;
	if (!doctype || !docname) return html;
	try {
		const r = await frappe.call({
			method: "frappe.utils.print_format_generator.render_jinja_template",
			args: { template: html, doctype, docname },
			silent: 1,
		});
		return r.message ?? html;
	} catch {
		return null;
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
		// Linked-list traversal so promoted children are visited immediately
		let child = node.firstChild;
		while (child) {
			const next = child.nextSibling;
			if (child.nodeType === Node.TEXT_NODE) {
				child = next;
				continue;
			}
			if (child.nodeType !== Node.ELEMENT_NODE) {
				child.remove();
				child = next;
				continue;
			}
			if (!SAFE_HTML_TAGS.has(child.tagName.toLowerCase())) {
				const first_promoted = child.firstChild;
				child.replaceWith(...child.childNodes);
				// Continue from first promoted child so they are sanitized too
				child = first_promoted || next;
				continue;
			}
			for (const attr of [...child.attributes]) {
				const name = attr.name.toLowerCase();
				if (!SAFE_HTML_ATTRS.has(name) || name.startsWith("on")) {
					child.removeAttribute(attr.name);
				} else if (name === "src") {
					const val = attr.value.trim();
					const is_data_image = /^data:image\//i.test(val);
					const is_relative =
						!val.startsWith("//") && !/^[a-z][a-z0-9+\-.]*:/i.test(val);
					const is_same_origin =
						typeof window !== "undefined" &&
						val.startsWith(window.location.origin + "/");
					if (!is_data_image && !is_relative && !is_same_origin)
						child.removeAttribute(attr.name);
				} else if (name === "href") {
					if (!/^https?:/i.test(attr.value.trim())) child.removeAttribute(attr.name);
				}
			}
			clean(child);
			child = next;
		}
	})(root);
	return root.innerHTML;
}

export function evaluate_visible_if(expr, doc) {
	if (!expr || !expr.trim()) return true;
	try {
		// eslint-disable-next-line no-new-func
		return !!new Function("doc", `return (${expr})`)(doc);
	} catch {
		return true;
	}
}

export function get_image_dimensions(src) {
	return new Promise((resolve, reject) => {
		let img = new Image();
		img.onload = function () {
			resolve({ width: this.width, height: this.height });
		};
		// a broken src must reject, not leave the caller hanging forever
		img.onerror = () => reject(new Error(`could not load image: ${src}`));
		img.src = src;
	});
}

// Option lists shared by the inspectors
export function value_field_opts(fields) {
	return (fields || [])
		.filter((f) => !frappe.model.no_value_type.includes(f.fieldtype))
		.map((f) => ({ label: f.label || f.fieldname, value: f.fieldname }));
}

export function table_field_opts(fields) {
	return (fields || [])
		.filter((f) => f.fieldtype === "Table")
		.map((f) => ({ label: f.label || f.fieldname, value: f.fieldname }));
}
