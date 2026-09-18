<template>
	<Teleport to="body">
		<div class="pfb-compare" tabindex="-1" ref="root">
			<div class="pfb-compare-stage">
				<div v-if="!docname" class="pfb-compare-empty">
					{{ __("Pick a record in the toolbar above to compare it.") }}
				</div>
				<div v-else-if="note" class="pfb-compare-empty">{{ note }}</div>
				<div v-else-if="!html" class="pfb-compare-empty">
					<span class="pfb-compare-spinner" aria-hidden="true"></span>
				</div>
				<iframe
					v-else
					ref="frame"
					class="pfb-compare-frame"
					:srcdoc="html"
					@load="mark_frame"
				></iframe>
			</div>

			<div class="pfb-compare-panel">
				<div class="pfb-compare-head">
					<div>
						<div class="pfb-compare-title">{{ __("Review changes") }}</div>
						<div class="pfb-compare-summary">{{ summary }}</div>
					</div>
					<button
						class="es-button"
						data-variant="ghost"
						data-icon-button="true"
						:title="__('Close')"
						@click="$emit('close')"
						v-html="frappe.utils.icon('x', 'sm')"
					></button>
				</div>
				<div class="pfb-compare-list">
					<div v-if="!entries.length" class="pfb-compare-none">
						{{ __("This draft matches the saved version.") }}
					</div>
					<template v-for="group in groups" :key="group.title">
						<div
							v-if="group.items.length"
							class="pfb-insp-section-label pfb-compare-group"
						>
							{{ group.title }}
						</div>
						<div
							v-for="item in group.items"
							:key="item.id"
							class="pfb-compare-item"
							:class="{ 'pfb-compare-item--jump': item.selector }"
							@click="item.selector && jump(item)"
							@mouseenter="item.selector && hover(item, true)"
							@mouseleave="item.selector && hover(item, false)"
						>
							<span class="pfb-compare-marker" :data-kind="item.kind">{{
								item.n
							}}</span>
							<span class="pfb-compare-item-body">
								<span class="pfb-compare-item-label">{{ item.label }}</span>
								<span
									v-for="line in item.lines"
									:key="line"
									class="pfb-compare-item-line"
								>
									{{ line }}
								</span>
							</span>
						</div>
					</template>
				</div>
			</div>
		</div>
	</Teleport>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from "vue";
import { useStore } from "../stores";
import { describe_draft_changes } from "../composables/useDraftDiff";

const emit = defineEmits(["close"]);
let { print_format, store } = useStore();

const root = ref(null);
const frame = ref(null);
const html = ref("");
const note = ref("");
const entries = ref([]);
let load_seq = 0;

const MARK_CSS = `
[data-pfb-diff] { position: relative; outline-offset: 2px; }
[data-pfb-diff]::before { content: attr(data-pfb-n); position: absolute; top: -9px; left: -9px; z-index: 1; min-width: 18px; height: 18px; padding: 0 5px; border-radius: 9px; font: 700 10px/18px sans-serif; text-align: center; color: #fff; box-shadow: 0 1px 2px rgba(0,0,0,.25); }
[data-pfb-diff="added"] { outline: 2px solid #16a34a; background: #ecfdf3; }
[data-pfb-diff="added"]::before { background: #16a34a; }
[data-pfb-diff="removed"] { outline: 2px dashed #dc2626; background: #fef2f2; text-decoration: line-through; opacity: 0.75; }
[data-pfb-diff="removed"]::before { background: #dc2626; text-decoration: none; }
[data-pfb-diff="changed"] { outline: 2px solid #d97706; background: #fffbeb; }
[data-pfb-diff="changed"]::before { background: #d97706; }
[data-pfb-diff="moved"] { outline: 2px dashed #6b7280; }
[data-pfb-diff="moved"]::before { background: #6b7280; }
[data-pfb-diff].pfb-diff-hot { box-shadow: 0 0 0 6px rgba(217, 119, 6, 0.3); }
.pfb-diff-band { position: absolute; z-index: 1; pointer-events: none; background: repeating-linear-gradient(45deg, rgba(217,119,6,.28) 0 4px, rgba(217,119,6,.12) 4px 8px); }
.pfb-diff-band > span, .pfb-diff-badge, .pfb-diff-ghost > span { position: absolute; top: 0; left: 0; padding: 0 4px; font: 600 9px/14px sans-serif; white-space: nowrap; color: #fff; background: #d97706; border-radius: 0 0 3px 0; }
.pfb-diff-ghost { position: absolute; z-index: 1; pointer-events: none; outline: 2px dashed #6b7280; outline-offset: -2px; }
.pfb-diff-ghost > span { background: #6b7280; }
.pfb-diff-badge { top: auto; bottom: 100%; left: auto; right: 0; margin-bottom: 2px; border-radius: 3px; display: flex; align-items: center; gap: 4px; }
.pfb-diff-swatch { display: inline-block; width: 10px; height: 10px; border: 1px solid #fff; border-radius: 2px; vertical-align: middle; }
.pfb-diff-old-label { text-decoration: line-through; opacity: .6; margin-right: 4px; }
.action-banner { display: none !important; }`;

const KIND_WORD = {
	added: __("added"),
	removed: __("removed"),
	changed: __("changed"),
	moved: __("moved"),
};
const SPACING = new Set([
	"padding",
	"margin",
	"gap",
	"label_gap",
	"cell_padding",
	"radius",
	"table_cell_padding",
	"table_radius",
	"table_min_height",
	"height",
]);
const COLOUR = new Set([
	"background",
	"label_color",
	"value_color",
	"border_color",
	"table_border_color",
	"table_header_bg",
	"color",
]);
const TEXT = new Set(["font_size", "bold", "text"]);
const LAYOUT = new Set([
	"align",
	"label_justify",
	"justify",
	"field_orientation",
	"field_borders",
	"grid_borders",
	"table_header",
	"table_style",
	"merge_direction",
	"page_break",
	"keep_together",
]);
const LABEL_DISPLAY = new Set(["show_label", "hide_colon", "show_empty", "show_text"]);

let docname = computed(() => store.value.preview_doc_name);
let doctype = computed(() => print_format.value.doc_type);
let summary = computed(() => {
	const n = entries.value.length;
	if (!n) return "";
	const counts = ["added", "changed", "moved", "removed"]
		.map((k) => [k, entries.value.filter((e) => e.kind === k).length])
		.filter(([, c]) => c)
		.map(([k, c]) => `${c} ${KIND_WORD[k]}`);
	return `${__("{0} changes", [n])} · ${counts.join(" · ")}`;
});
let groups = computed(() => [
	{ title: __("Print settings"), items: entries.value.filter((e) => e.group === "settings") },
	{ title: __("Sections"), items: entries.value.filter((e) => e.group === "sections") },
	{ title: __("Fields"), items: entries.value.filter((e) => e.group === "fields") },
]);

function setting_label(key) {
	return frappe.meta.get_docfield("Print Format", key)?.label || frappe.unscrub(key);
}

function value_text(v) {
	if (v == null || v === "") return __("default");
	if (typeof v === "boolean") return v ? __("on") : __("off");
	return String(v);
}

function field_name(f) {
	if (f.fieldtype === "Table") return __("{0} table", [f.label || f.fieldname]);
	if (f.fieldtype === "Repeater") return __("{0} custom table", [f.label || f.fieldname]);
	if (f.custom) return f.label || frappe.unscrub(f.fieldtype);
	return frappe.meta.get_label(doctype.value, f.fieldname) || f.label || f.fieldname;
}

function section_name(section, index) {
	return section.label || __("Section {0}", [index + 1]);
}

function sentences(changes) {
	const lines = new Set();
	for (const c of changes) {
		if (c.key === "column") {
			if (c.kind === "added") lines.add(__("Column '{0}' added", [c.column]));
			else if (c.kind === "removed") lines.add(__("Column '{0}' removed", [c.column]));
			else {
				const keys = new Set((c.changes || []).map((x) => x.key));
				if (keys.has("merged_fields"))
					lines.add(__("Column '{0}' shows different fields", [c.column]));
				if (keys.has("width")) lines.add(__("Column '{0}' resized", [c.column]));
				if (keys.has("label")) lines.add(__("Column '{0}' renamed", [c.column]));
				if (![...keys].some((k) => ["merged_fields", "width", "label"].includes(k))) {
					lines.add(__("Column '{0}' changed", [c.column]));
				}
			}
		} else if (c.key === "label") {
			lines.add(
				__("Label changed from '{0}' to '{1}'", [
					value_text(c.before),
					value_text(c.after),
				])
			);
		} else if (c.key === "columns") lines.add(__("Number of columns changed"));
		else if (SPACING.has(c.key)) lines.add(__("Spacing changed"));
		else if (COLOUR.has(c.key)) lines.add(__("Colours changed"));
		else if (TEXT.has(c.key)) lines.add(__("Text style changed"));
		else if (LAYOUT.has(c.key)) lines.add(__("Alignment or layout changed"));
		else if (LABEL_DISPLAY.has(c.key)) lines.add(__("Label display changed"));
		else if (c.key === "width") lines.add(__("Size changed"));
		else if (c.key === "custom_style") lines.add(__("Custom style changed"));
		else if (
			c.key === "visible_if" ||
			c.key === "row_condition" ||
			c.key === "column_condition"
		) {
			lines.add(__("Visibility rule changed"));
		} else if (c.key === "link_path" || c.key === "source")
			lines.add(__("Data source changed"));
		else lines.add(__("{0} changed", [frappe.unscrub(c.key)]));
	}
	return [...lines];
}

function inject(target, css) {
	const doc = target?.contentDocument;
	if (!doc?.head) return;
	const style = doc.createElement("style");
	style.textContent = css;
	doc.head.appendChild(style);
}

function find(item) {
	const doc = frame.value?.contentDocument;
	if (!doc) return null;
	return doc.querySelectorAll(item.selector)[item.occurrence || 0] || null;
}

const BOX_KEYS = { padding: "padding", margin: "margin" };
const GAP_KEYS = new Set(["gap"]);
const TEXT_BADGE = new Set([
	"font_size",
	"bold",
	"align",
	"label_justify",
	"justify",
	"columns",
	"field_orientation",
	"show_label",
	"hide_colon",
	"show_empty",
	"radius",
	"cell_padding",
	"table_cell_padding",
	"table_radius",
	"table_min_height",
	"height",
	"label_gap",
]);

function box_text(v) {
	if (v && typeof v === "object")
		return ["top", "right", "bottom", "left"].map((k) => v[k] || 0).join(" ");
	return value_text(v);
}

function make(doc, cls, text) {
	const div = doc.createElement("div");
	div.className = cls;
	if (text) {
		const label = doc.createElement("span");
		label.textContent = text;
		div.appendChild(label);
	}
	return div;
}

function place(node, style) {
	Object.assign(node.style, style);
	return node;
}

function draw_box_bands(el, key, change) {
	const doc = el.ownerDocument;
	const cs = doc.defaultView.getComputedStyle(el);
	const side = (k) => parseFloat(cs[`${key}-${k}`]) || 0;
	const t = side("top"),
		r = side("right"),
		b = side("bottom"),
		l = side("left");
	const text = `${frappe.unscrub(key)} ${box_text(change.after)} (${__("was")} ${box_text(
		change.before
	)})`;
	const inside = key === "padding";
	const bands = inside
		? [
				{ top: 0, left: 0, right: 0, height: `${t}px` },
				{ bottom: 0, left: 0, right: 0, height: `${b}px` },
				{ top: 0, bottom: 0, left: 0, width: `${l}px` },
				{ top: 0, bottom: 0, right: 0, width: `${r}px` },
		  ]
		: [
				{ top: `-${t}px`, left: `-${l}px`, right: `-${r}px`, height: `${t}px` },
				{ bottom: `-${b}px`, left: `-${l}px`, right: `-${r}px`, height: `${b}px` },
				{ top: 0, bottom: 0, left: `-${l}px`, width: `${l}px` },
				{ top: 0, bottom: 0, right: `-${r}px`, width: `${r}px` },
		  ];
	bands.forEach((style, i) => {
		const size = i < 2 ? parseFloat(style.height) : parseFloat(style.width);
		if (!size) return;
		el.appendChild(place(make(doc, "pfb-diff-band", i === 0 ? text : ""), style));
	});
	if (!t) el.appendChild(place(make(doc, "pfb-diff-badge", text), {}));
}

function draw_gap_bands(el, change) {
	const doc = el.ownerDocument;
	const row = el.querySelector(".section-columns");
	if (!row) return;
	const base = el.getBoundingClientRect();
	const cols = [...row.children].map((c) => c.getBoundingClientRect());
	const text = `${__("Gap")} ${value_text(change.after)} (${__("was")} ${value_text(
		change.before
	)})`;
	cols.slice(1).forEach((rect, i) => {
		const prev = cols[i];
		el.appendChild(
			place(make(doc, "pfb-diff-band", i === 0 ? text : ""), {
				top: `${prev.top - base.top}px`,
				left: `${prev.right - base.left}px`,
				width: `${rect.left - prev.right}px`,
				height: `${prev.height}px`,
			})
		);
	});
}

function draw_ghost_width(el, change) {
	const doc = el.ownerDocument;
	const before = String(change.before || "");
	if (!before) return;
	el.appendChild(
		place(make(doc, "pfb-diff-ghost", `${__("was")} ${before}`), {
			top: 0,
			left: 0,
			height: `${el.getBoundingClientRect().height}px`,
			width: before,
		})
	);
}

function draw_colours(el, changes) {
	const doc = el.ownerDocument;
	const badge = make(doc, "pfb-diff-badge");
	for (const c of changes) {
		const label = doc.createElement("span");
		label.textContent = `${frappe.unscrub(c.key)} `;
		badge.appendChild(label);
		for (const [v, arrow] of [
			[c.before, " → "],
			[c.after, ""],
		]) {
			const sw = doc.createElement("i");
			sw.className = "pfb-diff-swatch";
			sw.style.background = v || "transparent";
			badge.appendChild(sw);
			if (arrow) badge.appendChild(doc.createTextNode(arrow));
		}
	}
	el.appendChild(badge);
}

function draw_old_label(el, change) {
	const label = el.querySelector(".label, .section-label");
	if (!label) return;
	const old = el.ownerDocument.createElement("span");
	old.className = "pfb-diff-old-label";
	old.textContent = value_text(change.before);
	label.prepend(old);
}

function annotate(el, item) {
	const changes = item.changes || [];
	const colours = changes.filter((c) => COLOUR.has(c.key));
	if (colours.length) draw_colours(el, colours);
	const badges = [];
	for (const c of changes) {
		if (BOX_KEYS[c.key]) draw_box_bands(el, c.key, c);
		else if (GAP_KEYS.has(c.key)) draw_gap_bands(el, c);
		else if (c.key === "width") draw_ghost_width(el, c);
		else if (c.key === "label") draw_old_label(el, c);
		else if (TEXT_BADGE.has(c.key)) {
			badges.push(
				`${frappe.unscrub(c.key)} ${value_text(c.before)} → ${value_text(c.after)}`
			);
		}
	}
	if (badges.length && !colours.length)
		el.appendChild(make(el.ownerDocument, "pfb-diff-badge", badges.join(" · ")));
}

function mark_frame() {
	inject(frame.value, MARK_CSS);
	for (const item of entries.value) {
		const el = item.selector && find(item);
		if (!el) continue;
		el.setAttribute("data-pfb-diff", item.kind);
		el.setAttribute("data-pfb-n", item.n);
		el.title = [item.label, ...item.lines].join("\n");
		annotate(el, item);
	}
}

function hover(item, on) {
	find(item)?.classList.toggle("pfb-diff-hot", on);
}

function jump(item) {
	find(item)?.scrollIntoView({ block: "center", behavior: "smooth" });
}

async function load() {
	const seq = ++load_seq;
	html.value = "";
	note.value = "";
	const draft = store.value.get_preview_format_doc();
	const diff = describe_draft_changes(store.value.saved_format || {}, draft);
	let n = 0;
	entries.value = [
		...diff.settings.map((s) => ({
			id: `s${s.key}`,
			group: "settings",
			kind: "changed",
			label: setting_label(s.key),
			lines: [`${value_text(s.before)} → ${value_text(s.after)}`],
		})),
		...diff.sections.map((s) => ({
			id: `sec${s.index}`,
			group: "sections",
			kind: s.kind,
			label: section_name(s.section, s.index),
			lines: s.kind === "changed" ? sentences(s.changes) : [],
			changes: s.changes,
			selector: `[data-section="${s.index}"]`,
		})),
		...diff.fields.map((f, i) => ({
			id: `f${i}`,
			group: "fields",
			kind: f.kind,
			label: field_name(f.field),
			lines: sentences(f.changes),
			changes: f.changes,
			selector: `[data-fieldname="${f.field.fieldname}"]`,
			occurrence: f.occurrence,
		})),
	].map((e) => ({ ...e, n: e.selector ? ++n : "" }));
	try {
		const args = {
			print_format: { ...draft, format_data: JSON.stringify(diff.merged) },
			doctype: doctype.value,
			name: docname.value,
		};
		if (store.value.letterhead) args.letterhead = store.value.letterhead.name;
		const rendered = await frappe.xcall(
			"frappe.utils.print_format_generator.render_builder_preview",
			args
		);
		if (seq === load_seq) html.value = rendered;
	} catch (e) {
		if (seq === load_seq) note.value = e.message || __("Could not render the draft");
	}
}

function on_keydown(e) {
	if (e.key === "Escape" && !window.cur_dialog?.display) emit("close");
}

watch(docname, load);
onMounted(() => {
	root.value?.focus();
	load();
	window.addEventListener("keydown", on_keydown);
});
onUnmounted(() => window.removeEventListener("keydown", on_keydown));
</script>

<style scoped>
.pfb-compare {
	position: fixed;
	inset: 0;
	z-index: 1035;
	display: flex;
	background: var(--bg-color);
	outline: none;
}

.pfb-compare-stage {
	flex: 1;
	min-width: 0;
	display: flex;
	flex-direction: column;
	padding: 12px;
}

.pfb-compare-frame {
	flex: 1;
	width: 100%;
	min-height: 0;
	border: 1px solid var(--border-color);
	border-radius: var(--radius-lg, 8px);
	background: var(--fg-color);
}

.pfb-compare-empty {
	flex: 1;
	display: flex;
	align-items: center;
	justify-content: center;
	font-size: var(--text-sm);
	color: var(--text-muted);
}

.pfb-compare-panel {
	width: 320px;
	flex-shrink: 0;
	display: flex;
	flex-direction: column;
	border-left: 1px solid var(--border-color);
	background: var(--fg-color);
}

.pfb-compare-head {
	display: flex;
	align-items: flex-start;
	justify-content: space-between;
	gap: 8px;
	padding: 12px 10px 10px 14px;
	border-bottom: 1px solid var(--border-color);
}

.pfb-compare-title {
	font-size: var(--text-base);
	font-weight: var(--weight-semibold);
}

.pfb-compare-summary {
	margin-top: 2px;
	font-size: var(--text-sm);
	color: var(--text-muted);
}

.pfb-compare-list {
	flex: 1;
	overflow-y: auto;
	padding: 6px 8px 12px;
}

.pfb-compare-none {
	padding: 8px 6px;
	font-size: var(--text-sm);
	color: var(--text-muted);
}

.pfb-compare-group {
	padding: 10px 6px 4px;
}

.pfb-compare-item {
	display: flex;
	align-items: flex-start;
	gap: 10px;
	padding: 7px 6px;
	border-radius: var(--radius);
}

.pfb-compare-item--jump {
	cursor: pointer;
}

.pfb-compare-item--jump:hover {
	background: var(--gray-100);
}

.pfb-compare-marker {
	flex-shrink: 0;
	min-width: 20px;
	height: 20px;
	padding: 0 6px;
	border-radius: 10px;
	font-size: var(--text-tiny);
	font-weight: var(--weight-bold);
	line-height: 20px;
	text-align: center;
	color: var(--white);
	background: var(--gray-500);
}

.pfb-compare-marker[data-kind="added"] {
	background: #16a34a;
}

.pfb-compare-marker[data-kind="removed"] {
	background: #dc2626;
}

.pfb-compare-marker[data-kind="changed"] {
	background: #d97706;
}

.pfb-compare-item-body {
	min-width: 0;
	display: flex;
	flex-direction: column;
	gap: 2px;
}

.pfb-compare-item-label {
	font-size: var(--text-sm);
	font-weight: var(--weight-medium);
	color: var(--text-color);
}

.pfb-compare-item-line {
	font-size: var(--text-xs);
	color: var(--text-muted);
	overflow-wrap: anywhere;
}

.pfb-compare-spinner {
	width: 20px;
	height: 20px;
	border: 2px solid var(--gray-300);
	border-top-color: var(--gray-600);
	border-radius: 50%;
	animation: pfb-compare-spin 0.7s linear infinite;
}

@keyframes pfb-compare-spin {
	to {
		transform: rotate(360deg);
	}
}
</style>
