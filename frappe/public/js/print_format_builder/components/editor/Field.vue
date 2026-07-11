<template>
	<div
		:class="[
			preview_doc ? preview_root_classes : 'field field--chip',
			{
				'field--table': df.fieldtype == 'Table',
				'field--selected': is_selected,
				'field--preview': !!preview_doc,
				'field--condition-hidden': preview_doc && !is_field_visible,
			},
		]"
		:style="preview_doc ? preview_root_style : undefined"
		:data-fieldname="preview_data_attr(df.fieldname)"
		:data-fieldtype="preview_data_attr(df.fieldtype)"
		v-show="!df.remove"
		:title="df.label || df.fieldname"
		@click.stop="select_field"
	>
		<!-- ── Preview mode: show actual doc values ─────────── -->
		<template v-if="preview_doc">
			<!-- Handle HTML fields: render Jinja2 server-side if needed -->
			<div v-if="df.fieldtype == 'HTML' && df.html" v-html="rendered_html ?? df.html"></div>
			<!-- Spacer/Divider: the root element itself is the rendered output -->
			<i
				v-else-if="df.fieldtype == 'Spacer' || df.fieldtype == 'Divider'"
				v-show="false"
			></i>
			<template v-else-if="df.fieldtype == 'Image'">
				<img
					v-if="df.image_url || preview_doc[df.fieldname]"
					:src="df.image_url || preview_doc[df.fieldname]"
					:style="{ maxWidth: '100%', ...(df.width ? { width: df.width } : {}) }"
					:alt="df.label || ''"
				/>
				<span v-else class="text-muted">{{ __("No image — set one in the panel") }}</span>
			</template>
			<template v-else-if="df.fieldtype == 'Barcode' && df.custom">
				<img
					v-if="df.barcode_format == 'QR' && qr_src"
					:src="qr_src"
					:style="{ width: df.width || '35mm' }"
				/>
				<div
					v-else-if="barcode_svg"
					class="pf-barcode-svg"
					:style="df.width ? { width: df.width } : {}"
					v-html="barcode_svg"
				></div>
				<span
					v-else-if="barcode_raw_value && df.barcode_format !== 'QR'"
					class="text-muted"
					>{{ __("Invalid value for {0}", [df.barcode_format || "CODE128"]) }}</span
				>
				<span v-else class="text-muted">{{
					__("No barcode value — set one in the panel")
				}}</span>
			</template>
			<div
				v-else-if="df.fieldtype == 'Field Template'"
				v-html="rendered_template || ''"
			></div>
			<!-- Table MultiSelect field: render as a comma-separated value list -->
			<template v-else-if="df.fieldtype == 'Table MultiSelect'">
				<div
					v-if="df.label && df.show_label !== 'hide'"
					class="label"
					:style="label_text_style(df)"
				>
					{{ df.label }}
				</div>
				<div
					class="value"
					:class="{ 'text-muted': !(preview_doc[df.fieldname] || []).length }"
					:style="value_text_style(df)"
				>
					{{ multiselect_display(df) }}
				</div>
			</template>
			<!-- Table field -->
			<template v-else-if="df.fieldtype == 'Table'">
				<div v-if="df.label && df.show_label !== 'hide'" class="label">
					{{ df.label }}
				</div>
				<!-- radius lives on a wrapper: border-radius is a no-op on a
				     border-collapse:collapse table, same as the PDF markup -->
				<div
					:style="
						df.table_radius != null
							? { borderRadius: df.table_radius + 'px', overflow: 'hidden' }
							: {}
					"
				>
					<table
						class="table"
						:class="{ 'table-bordered': df.table_bordered !== false }"
					>
						<thead v-if="df.table_header !== 'none'">
							<!-- inline !important mirrors the server markup: the shared
								     stylesheet's own !important rules must lose to these -->
							<tr
								:style="
									df.table_header_bg
										? `background-color: ${df.table_header_bg} !important`
										: ''
								"
							>
								<th
									v-for="col in df.table_columns"
									:key="col.fieldname"
									class="column-header"
									:class="{ 'column-value--merged': has_merge(col) }"
									:data-fieldtype="col.fieldtype"
									:data-fieldname="col.fieldname"
									:style="
										(col.width ? `width: ${col.width}%; ` : '') +
										cell_style(df)
									"
								>
									{{ col.label || col.fieldname }}
								</th>
							</tr>
						</thead>
						<tbody>
							<tr
								v-for="(row, i) in (preview_doc[df.fieldname] || []).slice(0, 4)"
								:key="i"
								:class="i % 2 === 0 ? 'odd' : 'even'"
							>
								<td
									v-for="col in df.table_columns"
									:key="col.fieldname"
									class="column-value"
									:class="{ 'column-value--merged': has_merge(col) }"
									:data-fieldtype="col.fieldtype"
									:data-fieldname="col.fieldname"
									:style="cell_style(df)"
								>
									<!-- Merged cell: image (if any) floats left, text lines stack -->
									<div v-if="has_merge(col)" class="cell-merged">
										<template v-if="image_merge(col)">
											<img
												v-if="cell_image(col, row)"
												:src="cell_image(col, row)"
												class="cell-thumb-img"
												:style="thumb_box(col)"
												:alt="col.label || col.fieldname"
											/>
											<span
												v-else
												class="cell-thumb"
												:style="thumb(col, row).style"
												>{{ thumb(col, row).abbr }}</span
											>
										</template>
										<div class="cell-lines">
											<div
												v-for="(mf, mi) in text_merges(col)"
												:key="mi"
												class="cell-line"
												:class="`cell-line--${mf.style || 'primary'}`"
											>
												{{ format_merged(row, mf.fieldname) }}
											</div>
										</div>
									</div>
									<!-- Single (default) -->
									<template v-else>
										<img
											v-if="
												is_image_field(col, row[col.fieldname]) &&
												row[col.fieldname]
											"
											:src="row[col.fieldname]"
											class="preview-table-img"
											:alt="col.label || col.fieldname"
										/>
										<div
											v-else-if="is_html_content_field(col)"
											class="preview-table-html"
											v-html="format_cell(row, col)"
										></div>
										<span v-else>{{ format_cell(row, col) }}</span>
									</template>
								</td>
							</tr>
							<tr v-if="!preview_doc[df.fieldname]?.length">
								<td
									:colspan="df.table_columns?.length || 1"
									class="text-muted"
									style="text-align: center; font-size: 11px; padding: 6px"
								>
									{{ __("No rows") }}
								</td>
							</tr>
							<tr v-if="(preview_doc[df.fieldname] || []).length > 4">
								<td
									:colspan="df.table_columns?.length || 1"
									class="text-muted"
									style="text-align: center; font-size: 11px; padding: 6px"
								>
									{{
										__(
											"+ {0} more rows in this document — all print in the real output",
											[preview_doc[df.fieldname].length - 4]
										)
									}}
								</td>
							</tr>
						</tbody>
					</table>
				</div>
			</template>
			<!-- Repeater field -->
			<template v-else-if="df.fieldtype == 'Repeater'">
				<div v-if="df.label && df.show_label !== 'hide'" class="label">
					{{ df.label }}
				</div>
				<table class="pfb-repeater-table">
					<colgroup>
						<col
							v-for="(col, ci) in df.repeater_columns || []"
							:key="ci"
							:style="col.width ? { width: col.width + '%' } : {}"
						/>
					</colgroup>
					<tbody>
						<tr
							v-for="(row, i) in (preview_doc[df.source] || []).slice(0, 6)"
							:key="i"
						>
							<td
								v-for="(col, ci) in df.repeater_columns || []"
								:key="ci"
								class="pfb-repeater-cell"
								:style="{
									textAlign: col.align || 'left',
									...(col.color ? { color: col.color } : {}),
								}"
							>
								{{ repeater_cell(col, row) }}
							</td>
						</tr>
						<tr v-if="!(preview_doc[df.source] || []).length">
							<td
								class="text-muted"
								style="text-align: center; font-size: 11px; padding: 6px"
							>
								{{ df.source ? __("No rows") : __("Pick a source table") }}
							</td>
						</tr>
						<tr v-if="(preview_doc[df.source] || []).length > 6">
							<td
								:colspan="df.repeater_columns?.length || 1"
								class="text-muted"
								style="text-align: center; font-size: 11px; padding: 6px"
							>
								{{
									__(
										"+ {0} more rows in this document — all print in the real output",
										[preview_doc[df.source].length - 6]
									)
								}}
							</td>
						</tr>
					</tbody>
				</table>
			</template>
			<!-- Regular field -->
			<template v-else>
				<div
					v-if="df.label && df.show_label !== 'hide'"
					class="label"
					:style="label_text_style(df)"
				>
					{{ df.label }}
				</div>
				<div
					class="value"
					:class="{ 'text-muted': !preview_value }"
					:style="value_text_style(df)"
				>
					<img
						v-if="df.fieldtype == 'Attach Image' && preview_doc[df.fieldname]"
						class="w-100"
						:src="preview_doc[df.fieldname]"
						:alt="df.label || df.fieldname"
					/>
					<a
						v-else-if="df.fieldtype == 'Attach' && preview_doc[df.fieldname]"
						:href="preview_doc[df.fieldname]"
						>{{ String(preview_doc[df.fieldname]).split("/").pop() }}</a
					>
					<template v-else-if="df.fieldtype == 'Color' && preview_doc[df.fieldname]">
						<div
							class="color-square"
							:style="{ backgroundColor: preview_doc[df.fieldname] }"
						></div>
						{{ preview_doc[df.fieldname] }}
					</template>
					<span v-else>{{ preview_value || "—" }}</span>
				</div>
			</template>
			<!-- Top-right actions pill: drag + remove -->
			<div class="field-preview-actions">
				<div
					class="drag-handle field-drag-handle"
					v-html="frappe.utils.icon('grip', 'xs')"
				></div>
				<button
					class="es-button"
					data-size="xs"
					data-variant="ghost"
					data-icon-button="true"
					:title="__('Copy')"
					@click.stop="store.copy_field(df)"
					v-html="frappe.utils.icon('copy', 'xs')"
				></button>
				<button
					class="es-button"
					data-size="xs"
					data-variant="ghost"
					data-theme="red"
					data-icon-button="true"
					@click.stop="df['remove'] = true"
					v-html="frappe.utils.icon('x', 'xs')"
				></button>
			</div>
		</template>

		<!-- ── Builder mode: labels + controls ──────────────── -->
		<template v-else>
			<div
				class="field-row"
				:style="{ textAlign: df.align || 'left', ...custom_style }"
				:class="{ 'field-row--lr': field_orientation === 'left-right' }"
			>
				<div
					class="drag-handle field-drag-handle"
					v-html="frappe.utils.icon('grip', 'xs')"
				></div>
				<div class="field-body">
					<div class="field-content">
						<div
							class="custom-html"
							v-if="df.fieldtype == 'HTML' && df.html"
							v-html="df.html"
						></div>
						<div class="custom-html" v-else-if="df.fieldtype == 'Field Template'">
							{{ df.label }}
						</div>
						<img
							v-else-if="df.fieldtype == 'Image' && df.custom && df.image_url"
							:src="df.image_url"
							class="pf-builder-thumb"
							:alt="df.label || ''"
						/>
						<input
							v-else-if="editing && df.fieldtype != 'HTML'"
							ref="label_input"
							class="label-input"
							type="text"
							:placeholder="__('Label')"
							v-model="df.label"
							@keydown.enter="editing = false"
							@blur="editing = false"
						/>
						<span v-else-if="df.label">{{ df.label }}</span>
						<i class="text-muted" v-else>{{ __("No Label") }} ({{ df.fieldname }})</i>
					</div>
					<div class="field-meta">
						<span class="es-badge">{{ short_fieldtype }}</span>
						<div class="field-actions">
							<button
								v-if="df.fieldtype == 'HTML'"
								class="es-button"
								data-size="xs"
								data-variant="ghost"
								data-icon-button="true"
								@click.stop="edit_html"
								v-html="frappe.utils.icon('pencil', 'sm')"
							></button>
							<button
								class="es-button"
								data-size="xs"
								data-variant="ghost"
								data-icon-button="true"
								:title="__('Copy')"
								@click.stop="store.copy_field(df)"
								v-html="frappe.utils.icon('copy', 'sm')"
							></button>
							<button
								class="es-button"
								data-size="xs"
								data-variant="ghost"
								data-theme="red"
								data-icon-button="true"
								@click.stop="df['remove'] = true"
								v-html="frappe.utils.icon('x', 'sm')"
							></button>
						</div>
					</div>
				</div>
			</div>
			<div v-if="df.fieldtype == 'Table'" class="table-preview">
				<div class="table-columns-list">
					<span
						class="table-col-chip"
						:class="{ 'table-col-chip--invalid': tf.invalid_width }"
						v-for="tf in df.table_columns"
						:key="tf.fieldname"
						:title="tf.label || tf.fieldname"
					>
						{{ tf.label || tf.fieldname }}
					</span>
					<span
						v-if="!df.table_columns || !df.table_columns.length"
						class="text-muted no-columns-hint"
					>
						{{ __("No columns configured") }}
					</span>
				</div>
				<button class="configure-columns-btn" @click.stop="configure_columns">
					<span v-html="frappe.utils.icon('settings-2', 'xs')"></span>
					{{ __("Configure Columns") }}
				</button>
			</div>
			<div v-if="df.fieldtype == 'Repeater'" class="table-preview">
				<div class="table-columns-list">
					<span v-if="df.source" class="table-col-chip">{{ df.source }}</span>
					<span v-else class="text-muted no-columns-hint">
						{{ __("No source table selected") }}
					</span>
				</div>
			</div>
		</template>
	</div>
</template>

<script setup>
import ConfigureColumnsVue from "../inspector/ConfigureColumns.vue";
import {
	render_jinja_html,
	sanitize_html,
	evaluate_visible_if,
	thumb_hue,
	parse_inline_style,
} from "../../utils";
import { createApp, ref, nextTick, watch, computed, inject } from "vue";
import JsBarcode from "jsbarcode";

const props = defineProps(["df", "field_orientation"]);

// Per-field text colour for the label and value lines.
function label_text_style(df) {
	return df.label_color ? { color: df.label_color } : {};
}
function value_text_style(df) {
	return df.value_color ? { color: df.value_color } : {};
}

let store = inject("$store");
let editing = ref(false);
let label_input = ref(null);
let rendered_html = ref(null);
let rendered_template = ref(null);

let custom_style = computed(() => parse_inline_style(props.df.custom_style));

let is_selected = computed(() => store.selected_field.value === props.df);
let preview_doc = computed(() => store.preview_doc.value);
let is_field_visible = computed(() => evaluate_visible_if(props.df.visible_if, preview_doc.value));

// Fieldtypes whose server macro is not the label/value field div (Data.html)
const NON_VALUE_FIELDTYPES = new Set([
	"Table",
	"Repeater",
	"HTML",
	"Field Template",
	"Spacer",
	"Divider",
	"Image",
	"Barcode",
]);

// In preview mode the root element IS the server element: these mirror the
// class/style/data-attribute output of templates/print_format/macros/*.html
// so every shared-stylesheet rule hits the canvas exactly like the PDF.
const preview_root_classes = computed(() => {
	const df = props.df;
	if (df.fieldtype === "Table") {
		return [
			"child-table",
			`child-table--${df.table_style || "lined"}`,
			df.table_bordered === false ? "child-table--borderless" : "",
			df.table_header === "plain" ? "child-table--plain-header" : "",
		];
	}
	if (df.fieldtype === "Repeater") return ["pfb-repeater"];
	if (df.fieldtype === "HTML") return ["custom-html"];
	if (df.fieldtype === "Field Template") return ["field-template"];
	if (df.fieldtype === "Spacer" || df.fieldtype === "Divider") return [];
	if (df.fieldtype === "Image" || df.fieldtype === "Barcode") {
		return [
			"field",
			df.fieldtype === "Image" ? "print-image" : "print-barcode",
			df.align ? `field-align-${df.align}` : "",
		];
	}
	const lr = props.field_orientation === "left-right";
	return [
		"field",
		lr ? "left-right" : "",
		!lr && df.show_label === "inline" ? "field-inline" : "",
		df.align ? `field-align-${df.align}` : "",
		lr && df.label_justify ? `field-justify-${df.label_justify}` : "",
	];
});

const preview_root_style = computed(() => {
	const df = props.df;
	if (df.fieldtype === "Spacer") return { height: "1em", ...custom_style.value };
	if (df.fieldtype === "Divider") {
		return {
			height: "1px",
			margin: "0.5em 0",
			borderBottom: "1px solid",
			borderBottomColor: "var(--dark-border-color)",
			...custom_style.value,
		};
	}
	const style = {};
	const inline = props.field_orientation === "left-right" || df.show_label === "inline";
	if (!NON_VALUE_FIELDTYPES.has(df.fieldtype) && inline && df.label_gap != null) {
		style.gap = df.label_gap + "px";
	}
	return { ...style, ...custom_style.value };
});

// Spacer/Divider carry no data attributes on the server either
function preview_data_attr(value) {
	if (!preview_doc.value || !value) return undefined;
	if (props.df.fieldtype === "Spacer" || props.df.fieldtype === "Divider") return undefined;
	return value;
}

// Render Jinja2 HTML fields server-side when in preview mode
watch(
	[preview_doc, () => props.df.html],
	async ([doc]) => {
		const html = props.df.html;
		if (!doc || !html || props.df.fieldtype !== "HTML") {
			rendered_html.value = null;
			return;
		}
		rendered_html.value = await render_jinja_html(
			html,
			store.meta.value?.name,
			store.preview_doc_name.value
		);
	},
	{ immediate: true }
);

// Render Field Template fields server-side when in preview mode
watch(
	[preview_doc, () => props.df.field_template],
	async ([doc]) => {
		if (!doc || props.df.fieldtype !== "Field Template" || !props.df.field_template) {
			rendered_template.value = null;
			return;
		}
		try {
			const tmpl = await frappe.db.get_value(
				"Print Format Field Template",
				props.df.field_template,
				"template"
			);
			const html = tmpl?.message?.template || "";
			rendered_template.value = await render_jinja_html(
				html,
				store.meta.value?.name,
				store.preview_doc_name.value
			);
		} catch {
			rendered_template.value = null;
		}
	},
	{ immediate: true }
);

// ── Barcode element (custom layout block) ─────────────────
let qr_src = ref(null);

let barcode_raw_value = computed(() => {
	if (props.df.fieldtype !== "Barcode" || !props.df.custom) return null;
	if (props.df.barcode_field) {
		return preview_doc.value?.[props.df.barcode_field] ?? null;
	}
	return props.df.barcode_value || null;
});

let barcode_svg = computed(() => {
	const value = barcode_raw_value.value;
	if (!value || props.df.barcode_format === "QR") return null;
	const str = String(value);
	if (str.startsWith("<svg")) return sanitize_html(str);
	const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
	try {
		JsBarcode(svg, str, {
			format: props.df.barcode_format || "CODE128",
			displayValue: props.df.show_text !== false,
			height: 40,
			margin: 0,
		});
		svg.setAttribute("width", "100%");
		return svg.outerHTML;
	} catch {
		return null;
	}
});

watch(
	[barcode_raw_value, () => props.df.barcode_format],
	frappe.utils.debounce(async ([value, format]) => {
		if (format !== "QR" || !value) {
			qr_src.value = null;
			return;
		}
		try {
			const r = await frappe.call("frappe.utils.print_format_generator.get_qr_code", {
				value: String(value),
			});
			qr_src.value = r.message || null;
		} catch {
			qr_src.value = null;
		}
	}, 300),
	{ immediate: true }
);

let preview_value = computed(() => {
	if (!preview_doc.value || !props.df.fieldname) return null;
	const raw = preview_doc.value[props.df.fieldname];
	if (raw === null || raw === undefined || raw === "") return null;
	const ft = props.df.fieldtype;
	// Check fields return an <input> element from frappe.format — handle directly
	if (ft === "Check") return raw ? __("Yes") : __("No");
	try {
		const formatted = frappe.format(raw, props.df, { only_value: true }, preview_doc.value);
		// If frappe.format returned HTML markup, extract the text content
		if (typeof formatted === "string" && formatted.includes("<")) {
			const tmp = document.createElement("div");
			tmp.innerHTML = formatted;
			return tmp.textContent || tmp.innerText || String(raw);
		}
		return formatted;
	} catch {
		return String(raw);
	}
});

const IMAGE_FIELDTYPES = new Set(["Attach Image", "Image", "Attach"]);
const IMAGE_EXTENSIONS = /\.(png|jpe?g|gif|webp|svg|bmp|ico)(\?.*)?$/i;
function is_image_field(col, value) {
	if (IMAGE_FIELDTYPES.has(col?.fieldtype)) return true;
	// Heuristic: any field whose value looks like an image URL
	if (value && typeof value === "string" && IMAGE_EXTENSIONS.test(value)) return true;
	return false;
}

const HTML_CONTENT_FIELDTYPES = new Set(["Text Editor", "Long Text"]);

// Cell padding + border colour as an inline style string; the border colour
// needs !important to beat the shared stylesheet's own !important border
// rules, exactly like the server markup (macros/Table.html) does.
function cell_style(df) {
	const parts = [];
	if (df.table_cell_padding != null) parts.push(`padding: ${df.table_cell_padding}px`);
	if (df.table_border_color) parts.push(`border-color: ${df.table_border_color} !important`);
	return parts.join("; ");
}

function repeater_cell(col, row) {
	return (col.template || [])
		.map((tok) => {
			if (tok.t === "s") return tok.v || "";
			const child_df = repeater_child_df(tok.v);
			return child_df ? format_cell(row || {}, child_df) : row?.[tok.v] ?? "";
		})
		.join("");
}

function repeater_child_df(fieldname) {
	const source = store.meta.value?.fields?.find((f) => f.fieldname === props.df.source);
	if (!source) return null;
	return frappe.get_meta(source.options)?.fields?.find((f) => f.fieldname === fieldname) || null;
}

function multiselect_display(df) {
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

function is_html_content_field(col) {
	return HTML_CONTENT_FIELDTYPES.has(col?.fieldtype);
}

function format_cell(row, col) {
	const raw = row[col.fieldname];
	if (raw === null || raw === undefined || raw === "") return "";
	if (col.fieldtype === "Check") return raw ? __("Yes") : __("No");
	// HTML content fields: sanitize then return for v-html rendering
	if (HTML_CONTENT_FIELDTYPES.has(col.fieldtype)) return sanitize_html(raw);
	try {
		const formatted = frappe.format(raw, col, { only_value: true }, row);
		if (typeof formatted === "string" && formatted.includes("<")) {
			const tmp = document.createElement("div");
			tmp.innerHTML = formatted;
			return tmp.textContent || tmp.innerText || String(raw);
		}
		return formatted;
	} catch {
		return String(raw);
	}
}

// ── Merged cell helpers ────────────────────────────────────
// Image fieldtypes that store a URL directly, so they can float left.
const MERGE_IMAGE_FIELDTYPES = new Set(["Attach Image", "Attach"]);

// The column's own field is always the implicit first (primary) line;
// col.merged_fields holds only the extra fields merged in beside it.
function merged_fields(col) {
	const extra = (col.merged_fields || []).filter((mf) => mf && mf.fieldname);
	if (!extra.length) return [];
	return [{ fieldname: col.fieldname, fieldtype: col.fieldtype, style: "primary" }, ...extra];
}

function has_merge(col) {
	return (col.merged_fields || []).length > 0;
}

// The first merged field that is an image — rendered on the left.
function image_merge(col) {
	return merged_fields(col).find((mf) => MERGE_IMAGE_FIELDTYPES.has(mf.fieldtype)) || null;
}

// Remaining fields render as stacked text lines.
function text_merges(col) {
	const img = image_merge(col);
	return merged_fields(col).filter((mf) => mf.fieldname !== img?.fieldname);
}

// Format a merged sub-field using its own child docfield definition.
// Merged lines are plain text, so strip any HTML kept for rich-text
// fields (Text Editor / Long Text) down to its text content.
function format_merged(row, fieldname) {
	const dcol = frappe.meta.get_docfield(props.df.options, fieldname) || {
		fieldname,
		fieldtype: "Data",
	};
	const val = format_cell(row, dcol);
	if (typeof val === "string" && val.includes("<")) {
		const tmp = document.createElement("div");
		tmp.innerHTML = val;
		return (tmp.textContent || tmp.innerText || "").trim();
	}
	return val;
}

function cell_image(col, row) {
	const img = image_merge(col);
	const v = img ? row[img.fieldname] : null;
	return typeof v === "string" && v ? v : null;
}

function thumb_box(col) {
	const s = (col.image_size || 40) + "px";
	return { width: s, height: s };
}

// Initials fallback (abbr + coloured box) when an image field is merged
// but the row has no image. Colour keyed off the first text field.
function thumb(col, row) {
	const raw = String(row[text_merges(col)[0]?.fieldname] ?? "");
	const hue = thumb_hue(raw);
	return {
		abbr: frappe.get_abbr(raw) || "?",
		style: {
			...thumb_box(col),
			fontSize: Math.round((col.image_size || 40) * 0.4) + "px",
			background: `hsl(${hue}, 65%, 92%)`,
			color: `hsl(${hue}, 55%, 35%)`,
		},
	};
}

function select_field() {
	store.selected_field.value = props.df;
	store.selected_letterhead.value = false;
	store.selected_lh_footer.value = false;
	if (props.df.fieldtype !== "HTML") {
		editing.value = true;
	}
}

let short_fieldtype = computed(() => {
	const map = {
		Data: "Data",
		Currency: "₹",
		Int: "Int",
		Float: "Float",
		Date: "Date",
		Datetime: "DateTime",
		Check: "Check",
		Select: "Select",
		Table: "Table",
		"Table MultiSelect": "Multi",
		"Long Text": "Text",
		Text: "Text",
		Link: "Link",
		Signature: "Sign",
		Attach: "File",
		"Attach Image": "Img",
		HTML: "HTML",
		Spacer: "Space",
		Divider: "Line",
		Image: "Img",
		Barcode: "Code",
		"Field Template": "Tmpl",
		Repeater: "Repeat",
	};
	return map[props.df.fieldtype] || props.df.fieldtype?.substring(0, 5) || "";
});

function edit_html() {
	let d = new frappe.ui.Dialog({
		title: __("Edit HTML"),
		fields: [{ label: __("HTML"), fieldname: "html", fieldtype: "Code", options: "HTML" }],
		primary_action: ({ html }) => {
			html = frappe.dom.remove_script_and_style(html);
			props.df["html"] = html;
			d.hide();
		},
	});
	d.set_value("html", props.df.html);
	d.show();
}

function configure_columns() {
	let dialog = new frappe.ui.Dialog({
		title: __("Configure columns for {0}", [props.df.label]),
		fields: [
			{ fieldtype: "HTML", fieldname: "columns_area" },
			{
				label: "",
				fieldtype: "Autocomplete",
				placeholder: __("Add Column"),
				fieldname: "add_column",
				options: get_all_columns(),
				onchange: () => {
					let fieldname = dialog.get_value("add_column");
					if (fieldname) {
						let column = get_column_to_add(fieldname);
						if (column) {
							props.df.table_columns.push(column);
							props.df["table_columns"] = props.df.table_columns;
							dialog.set_value("add_column", "");
						}
					}
				},
			},
		],
		on_page_show: () => {
			const app = createApp(ConfigureColumnsVue, { df: props.df });
			SetVueGlobals(app);
			app.mount(dialog.get_field("columns_area").$wrapper.get(0));
		},
		on_hide: () => {
			props.df["table_columns"] = props.df.table_columns.filter((col) => !col.invalid_width);
		},
	});
	dialog.show();
}

function get_all_columns() {
	let meta = frappe.get_meta(props.df.options);
	let more_columns = [{ label: __("Sr No."), value: "idx" }];
	return more_columns.concat(
		meta.fields
			.map((tf) => {
				if (frappe.model.no_value_type.includes(tf.fieldtype)) return;
				return { label: tf.label, value: tf.fieldname };
			})
			.filter(Boolean)
	);
}

function get_column_to_add(fieldname) {
	const standard = {
		idx: { label: __("Sr No."), fieldtype: "Data", fieldname: "idx", width: 10 },
	};
	if (fieldname in standard) return standard[fieldname];
	return { ...frappe.meta.get_docfield(props.df.options, fieldname), width: 10 };
}

function validate_table_columns() {
	if (props.df.fieldtype != "Table") return;
	let total = 0;
	for (let col of props.df.table_columns) {
		if (!col.width) col.width = 10;
		total += col.width;
		col.invalid_width = total > 100;
	}
}

watch(editing, (value) => {
	if (value) nextTick(() => label_input.value?.focus());
});
watch(
	() => props.df.table_columns,
	() => validate_table_columns(),
	{ deep: true }
);
</script>

<style scoped>
.field--chip {
	display: flex;
	flex-direction: column;
	gap: 0;
	width: 100%;
	min-width: 0;
	background-color: var(--bg-light-gray);
	border-radius: var(--radius);
	border: 1px dashed var(--gray-400);
	padding: 0.4rem 0.5rem;
	font-size: var(--text-sm);
	cursor: grab;
	overflow: hidden;
}

.field--chip:active {
	cursor: grabbing;
}

.field--chip.sortable-chosen,
.field--chip.sortable-ghost {
	cursor: grabbing;
}

.field--chip:focus-within {
	border-style: solid;
	border-color: var(--gray-600);
}

.field--chip.field--selected {
	border-style: solid;
	border-color: var(--gray-500);
}

.field-row {
	display: flex;
	align-items: center;
	gap: 0.25rem;
	width: 100%;
	min-width: 0;
}

.field-drag-handle {
	cursor: grab;
	color: var(--gray-400);
	display: flex;
	align-items: center;
	flex-shrink: 0;
}

.field-drag-handle:hover {
	color: var(--gray-600);
}

.field-body {
	flex: 1;
	min-width: 0;
	display: flex;
	align-items: center;
	justify-content: space-between;
	gap: 0.5rem;
}

.field-content {
	flex: 1;
	min-width: 0;
	overflow: hidden;
	text-overflow: ellipsis;
	white-space: nowrap;
}

.field-meta {
	display: flex;
	align-items: center;
	gap: 0.25rem;
	flex-shrink: 0;
}

.field-actions {
	display: flex;
	align-items: center;
	gap: 2px;
}

.field--chip .custom-html {
	word-break: break-all;
}

.label-input {
	background-color: transparent;
	border: none;
	padding: 0;
	width: 100%;
}

.label-input:focus {
	outline: none;
}

/* Table field preview */
.table-preview {
	margin-top: 0.5rem;
	padding-top: 0.5rem;
	border-top: 1px solid var(--gray-300);
	display: flex;
	flex-direction: column;
	gap: 0.4rem;
}

.table-columns-list {
	display: flex;
	flex-wrap: wrap;
	gap: 4px;
}

.table-col-chip {
	display: inline-block;
	background: var(--fg-color);
	border: 1px solid var(--gray-300);
	border-radius: var(--radius);
	padding: 1px 6px;
	font-size: var(--text-xs);
	color: var(--text-color);
	white-space: nowrap;
	max-width: 100px;
	overflow: hidden;
	text-overflow: ellipsis;
	vertical-align: middle;
}

.table-col-chip--invalid {
	border-color: var(--red-300);
	color: var(--red-500);
	background: var(--red-50);
}

.configure-columns-btn {
	align-self: flex-start;
	display: inline-flex;
	align-items: center;
	gap: 4px;
	font-size: var(--text-xs);
	font-weight: 500;
	color: var(--text-muted);
	background: var(--gray-50);
	border: 1px solid var(--gray-200);
	border-radius: var(--radius);
	padding: 3px 8px;
	cursor: pointer;
	outline: none;
	transition: color 0.15s, border-color 0.15s, background 0.15s;
	line-height: 1.4;
}

.configure-columns-btn:hover {
	color: var(--gray-800);
	border-color: var(--gray-400);
	background: var(--gray-100);
}

.configure-columns-btn:focus {
	outline: none;
	box-shadow: none;
}

.no-columns-hint {
	font-size: var(--text-xs);
}

/* ── Left-right label orientation (builder mode) ────────── */
.field-row--lr {
	flex-direction: row;
	align-items: center;
}

/* ── Preview mode ────────────────────────────────────────── */
.field--preview {
	position: relative;
	border-radius: var(--radius);
}

.field--condition-hidden {
	opacity: 0.35;
	border-radius: var(--radius);
}

/* Selection chrome is outline-only: it must never change the geometry
   of the previewed markup, which mirrors the printed page 1:1. */
.field--preview:hover {
	outline: 1px dashed var(--gray-400);
	outline-offset: 1px;
}

.field--preview.field--selected {
	outline: 1px solid var(--gray-400);
	outline-offset: 1px;
}

/* Top-right actions pill: drag + remove — hidden until hover/selected */
.field-preview-actions {
	display: none;
	position: absolute;
	top: 2px;
	right: 2px;
	z-index: 2;
	gap: 2px;
	background: var(--fg-color);
	border: 1px solid var(--border-color);
	border-radius: var(--radius);
	padding: 1px 2px;
	align-items: center;
	box-shadow: var(--shadow-xs);
}

.field--preview:hover .field-preview-actions,
.field--preview.field--selected .field-preview-actions {
	display: flex;
}

.field-preview-actions .field-drag-handle {
	cursor: grab;
	color: var(--gray-400);
	display: flex;
	align-items: center;
	padding: 2px;
}

.field-preview-actions .field-drag-handle:hover {
	color: var(--gray-600);
}

/* Table/repeater/merged-cell visuals come from the shared print stylesheet
   (templates/print_format/print_format_doc.css) via the .print-format-doc scope */
.preview-table-img {
	max-width: 100%;
	max-height: 100px;
}

.preview-table-html {
	word-break: break-word;
	white-space: normal;
}

.pf-barcode-svg {
	display: inline-block;
	max-width: 100%;
}

.pf-builder-thumb {
	max-height: 32px;
	max-width: 120px;
	object-fit: contain;
	border-radius: var(--radius);
	vertical-align: middle;
}
</style>
