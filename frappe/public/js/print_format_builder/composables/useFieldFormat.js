import { computed } from "vue";
import { sanitize_html, thumb_hue } from "../utils";

const IMAGE_FIELDTYPES = new Set(["Attach Image", "Image", "Attach"]);
const IMAGE_EXTENSIONS = /\.(png|jpe?g|gif|webp|svg|bmp|ico)(\?.*)?$/i;
const HTML_CONTENT_FIELDTYPES = new Set(["Text Editor", "Long Text"]);
const MERGE_IMAGE_FIELDTYPES = new Set(["Attach Image", "Attach"]);

export function useFieldFormat(props, store, preview_doc) {
	const preview_value = computed(() => {
		if (!preview_doc.value || !props.df.fieldname) return null;
		const raw = preview_doc.value[props.df.fieldname];
		if (raw === null || raw === undefined || raw === "") return null;
		const ft = props.df.fieldtype;
		if (ft === "Check") return raw ? __("Yes") : __("No");
		try {
			const formatted = frappe.format(
				raw,
				props.df,
				{ only_value: true },
				preview_doc.value
			);
			if (typeof formatted === "string" && formatted.includes("<")) {
				return frappe.utils.html2text(formatted) || String(raw);
			}
			return formatted;
		} catch {
			return String(raw);
		}
	});

	const preview_value_html = computed(() => {
		if (!preview_doc.value || !props.df.fieldname || props.df.fieldtype === "Check")
			return null;
		const server = store.preview_values.value?.[props.df.fieldname];
		if (server === null || server === undefined || server === "") return null;
		return sanitize_html(String(server));
	});

	// Same math as macros/Rating.html: value is a 0-1 fraction, df.options holds the star count
	const rating_stars = computed(() => {
		const total = parseInt(props.df.options) || 5;
		const value = (preview_doc.value && preview_doc.value[props.df.fieldname]) || 0;
		return { total, filled: Math.min(Math.floor(value * total + 0.5), total) };
	});

	function is_image_field(col, value) {
		if (IMAGE_FIELDTYPES.has(col?.fieldtype)) return true;
		if (value && typeof value === "string" && IMAGE_EXTENSIONS.test(value)) return true;
		return false;
	}

	// Border colour needs !important to beat the shared stylesheet's own !important
	// border rules, exactly like the server markup (macros/Table.html) does.
	function cell_style(df) {
		const parts = [];
		if (df.table_cell_padding != null) parts.push(`padding: ${df.table_cell_padding}px`);
		if (df.table_border_color) parts.push(`border-color: ${df.table_border_color} !important`);
		return parts.join("; ");
	}

	function repeater_cell(col, i, row) {
		return (col.template || [])
			.map((tok) => {
				if (tok.t === "s") return tok.v || "";
				const server = store.preview_child_values.value?.[props.df.source]?.[i]?.[tok.v];
				if (server !== null && server !== undefined && server !== "") {
					return frappe.utils.html2text(String(server));
				}
				const child_df = repeater_child_df(tok.v);
				return child_df ? format_cell(row || {}, child_df) : row?.[tok.v] ?? "";
			})
			.join("");
	}

	function repeater_child_df(fieldname) {
		const source = store.meta.value?.fields?.find((f) => f.fieldname === props.df.source);
		if (!source) return null;
		return (
			frappe.get_meta(source.options)?.fields?.find((f) => f.fieldname === fieldname) || null
		);
	}

	function multiselect_display(df) {
		const server = store.preview_values.value?.[df.fieldname];
		if (server !== null && server !== undefined && server !== "") {
			return frappe.utils.html2text(String(server));
		}
		const rows = preview_doc.value?.[df.fieldname] || [];
		if (!rows.length) return "—";
		const child_meta = frappe.get_meta(df.options);
		const link_field = child_meta?.fields.find((f) => f.fieldtype === "Link");
		if (!link_field) return "—";
		return (
			rows
				.map((r) => r[link_field.fieldname])
				.filter(Boolean)
				.join(", ") || "—"
		);
	}

	function cell_server_html(i, col) {
		const v = store.preview_child_values.value?.[props.df.fieldname]?.[i]?.[col.fieldname];
		if (v === null || v === undefined || v === "") return null;
		return sanitize_html(String(v));
	}

	function format_cell(row, col) {
		const raw = row[col.fieldname];
		if (raw === null || raw === undefined || raw === "") return "";
		if (col.fieldtype === "Check") return raw ? __("Yes") : __("No");
		if (HTML_CONTENT_FIELDTYPES.has(col.fieldtype)) return sanitize_html(raw);
		try {
			const formatted = frappe.format(raw, col, { only_value: true }, row);
			if (typeof formatted === "string" && formatted.includes("<")) {
				return frappe.utils.html2text(formatted) || String(raw);
			}
			return formatted;
		} catch {
			return String(raw);
		}
	}

	// The column's own field is always the implicit first (primary) line;
	// col.merged_fields holds only the extra fields merged in beside it.
	function merged_fields(col) {
		const extra = (col.merged_fields || []).filter((mf) => mf && mf.fieldname);
		if (!extra.length) return [];
		return [
			{ fieldname: col.fieldname, fieldtype: col.fieldtype, style: "primary" },
			...extra,
		];
	}

	function has_merge(col) {
		return (col.merged_fields || []).length > 0;
	}

	function image_merge(col) {
		return merged_fields(col).find((mf) => MERGE_IMAGE_FIELDTYPES.has(mf.fieldtype)) || null;
	}

	function text_merges(col) {
		const img = image_merge(col);
		return merged_fields(col).filter((mf) => mf.fieldname !== img?.fieldname);
	}

	function format_merged(row, i, fieldname) {
		const server = store.preview_child_values.value?.[props.df.fieldname]?.[i]?.[fieldname];
		if (server !== null && server !== undefined && server !== "") {
			return frappe.utils.html2text(String(server)).trim();
		}
		const dcol = frappe.meta.get_docfield(props.df.options, fieldname) || {
			fieldname,
			fieldtype: "Data",
		};
		const val = format_cell(row, dcol);
		if (typeof val === "string" && val.includes("<")) {
			return frappe.utils.html2text(val).trim();
		}
		return val;
	}

	function cell_image(col, row) {
		const img = image_merge(col);
		const v = img ? row[img.fieldname] : null;
		return typeof v === "string" && v ? v : null;
	}

	function thumb_box(col) {
		return { "--thumb-size": (col.image_size || 40) + "px" };
	}

	// Initials fallback when an image field is merged but the row has no image.
	function thumb(col, row) {
		const raw = String(row[text_merges(col)[0]?.fieldname] ?? "");
		const hue = thumb_hue(raw);
		return {
			abbr: frappe.get_abbr(raw) || "?",
			style: {
				...thumb_box(col),
				fontSize: Math.floor((col.image_size || 40) * 0.4) + "px",
				background: `hsl(${hue}, 65%, 92%)`,
				color: `hsl(${hue}, 55%, 35%)`,
			},
		};
	}

	return {
		preview_value,
		preview_value_html,
		rating_stars,
		is_image_field,
		cell_style,
		repeater_cell,
		multiselect_display,
		cell_server_html,
		format_cell,
		has_merge,
		image_merge,
		text_merges,
		format_merged,
		cell_image,
		thumb_box,
		thumb,
	};
}
