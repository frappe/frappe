<template>
	<div
		ref="root"
		:class="[
			preview_doc ? preview_root.classes : 'field field--chip',
			{
				'field--selected': is_selected,
				'field--layer-hover': store.hovered_node.value === df,
				'field--preview': !!preview_doc,
				'field--condition-hidden': preview_doc && !is_field_visible,
			},
		]"
		:style="preview_doc ? preview_root.style : undefined"
		:data-fieldname="preview_data_attr(df.fieldname)"
		:data-fieldtype="preview_data_attr(df.fieldtype)"
		:data-field-uid="field_uid(df)"
		v-show="!df.remove"
		:title="df.label || df.fieldname"
		:aria-label="df.label || df.fieldname"
		tabindex="0"
		@click.stop="select_field($event)"
		@mouseenter="store.hovered_field.value = df"
		@mouseleave="store.hovered_field.value = null"
		@keydown.enter.prevent="kbd_select($event)"
		@keydown.space.prevent="kbd_select($event)"
	>
		<!-- ── Preview mode: show actual doc values ─────────── -->
		<template v-if="preview_doc">
			<FieldPreview :df="df" />
			<SectionRadiusHandle v-if="show_radius_handle" :target="df" prop="table_radius" />
		</template>

		<FieldChip v-else ref="chip" :df="df" :field_orientation="field_orientation" />
	</div>
</template>

<script setup>
import { computed, inject, onMounted, onUnmounted, ref } from "vue";
import FieldPreview from "./FieldPreview.vue";
import FieldChip from "./FieldChip.vue";
import SectionRadiusHandle from "./SectionRadiusHandle.vue";
import { field_uid } from "../../utils";
import { useFieldRoot } from "./useFieldRoot";

const props = defineProps(["df", "field_orientation"]);
const store = inject("$store");
const chip = ref(null);

const preview_doc = computed(() => store.preview_doc.value);
const is_selected = computed(
	() => store.selected_field.value === props.df || store.selected_fields.value.includes(props.df)
);
const is_field_visible = computed(() => store.is_visible(props.df.visible_if));
// a table draws its own frame, so it takes the same corner handle a section has
const show_radius_handle = computed(
	() =>
		!!preview_doc.value &&
		props.df.fieldtype === "Table" &&
		is_selected.value &&
		store.selected_fields.value.length <= 1
);
const { preview_root, preview_data_attr } = useFieldRoot(props, preview_doc);

function select_field(e) {
	if (e && e.shiftKey && !e.metaKey && !e.ctrlKey) {
		store.select_field_range(props.df);
		return;
	}
	const additive = !!(e && (e.metaKey || e.ctrlKey));
	store.select_field(props.df, additive);
	if (!additive && props.df.fieldtype !== "HTML") chip.value?.edit();
}
function kbd_select(e) {
	if (e && e.shiftKey && !e.metaKey && !e.ctrlKey) {
		store.select_field_range(props.df);
		return;
	}
	store.select_field(props.df, !!(e.metaKey || e.ctrlKey));
}

const root = ref(null);
let context_menu = null;
// the section under this field binds its own menu, and the event bubbles there
const menu_options = [
	{ label: __("Copy"), icon: "copy", onclick: () => store.copy_field(props.df) },
	{
		label: __("Duplicate"),
		icon: "copy-plus",
		onclick: () => store.duplicate_field(props.df),
	},
	{
		label: __("Save as snippet"),
		icon: "bookmark-plus",
		onclick: () => store.prompt_snippet(props.df, "Field"),
	},
	{
		label: __("Paste"),
		icon: "clipboard-paste",
		condition: () => !!store.clipboard.value,
		onclick: () => store.paste_clipboard(),
	},
	{
		group: "",
		hide_label: true,
		options: [
			{
				label: __("Delete"),
				icon: "trash",
				theme: "red",
				onclick: () => store.remove_field(props.df),
			},
		],
	},
];

onMounted(() => {
	context_menu = new frappe.ui.ContextMenu({
		target: root.value,
		options: menu_options,
		on_open: (e) => {
			e.stopPropagation();
			store.select_field(props.df);
		},
	});
});
onUnmounted(() => context_menu?.destroy());
</script>

<style scoped>
.field--chip {
	position: relative;
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

.field--chip.sortable-chosen {
	cursor: grabbing;
}

.field--chip:focus-within {
	border-style: solid;
	border-color: var(--gray-600);
}

/* ── Left-right label orientation (builder mode) ────────── */

/* ── Preview mode ────────────────────────────────────────── */
.field--preview {
	position: relative;
}

.field--condition-hidden {
	opacity: 0.35;
}

.field--preview.field--selected::after,
.field--preview:hover::after,
.field--preview.field--layer-hover::after,
.field--chip.field--selected::after,
.field--chip:hover::after,
.field--chip.field--layer-hover::after {
	content: "";
	position: absolute;
	inset: 0;
	z-index: 1;
	border: var(--pfb-ring);
	border-radius: inherit;
	pointer-events: none;
}

:deep(.typst-block-source) {
	margin: 0;
	font-family: monospace;
	font-size: var(--text-xs);
	white-space: pre-wrap;
	word-break: break-word;
	color: var(--text-color);
	background: var(--surface-gray-1);
	border-radius: var(--radius-sm);
	padding: 4px 6px;
}
</style>
