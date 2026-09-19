<template>
	<div
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
		@contextmenu="on_context_menu"
		@mouseenter="store.hovered_field.value = df"
		@mouseleave="store.hovered_field.value = null"
		@keydown.enter.prevent="kbd_select($event)"
		@keydown.space.prevent="kbd_select($event)"
	>
		<!-- ── Preview mode: show actual doc values ─────────── -->
		<template v-if="preview_doc">
			<FieldPreview :df="df" />
			<div class="field-preview-actions">
				<div
					class="drag-handle field-drag-handle"
					v-html="frappe.utils.icon('grip', 'xs')"
				></div>
				<button
					class="es-button"
					data-size="xs"
					data-variant="ghost"
					data-theme="red"
					data-icon-button="true"
					:title="__('Remove field')"
					@click.stop="store.remove_field(df)"
					v-html="frappe.utils.icon('x', 'xs')"
				></button>
			</div>
		</template>

		<FieldChip v-else ref="chip" :df="df" :field_orientation="field_orientation" />
	</div>
</template>

<script setup>
import { computed, inject, ref } from "vue";
import FieldPreview from "./FieldPreview.vue";
import FieldChip from "./FieldChip.vue";
import { field_uid } from "../../utils";
import { useContextMenu } from "../../composables/useContextMenu";
import { useFieldRoot } from "./useFieldRoot";

const props = defineProps(["df", "field_orientation"]);
const store = inject("$store");
const chip = ref(null);

const preview_doc = computed(() => store.preview_doc.value);
const is_selected = computed(
	() => store.selected_field.value === props.df || store.selected_fields.value.includes(props.df)
);
const is_field_visible = computed(() => store.is_visible(props.df.visible_if));
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

const { open: open_context_menu } = useContextMenu();
function on_context_menu(e) {
	store.select_field(props.df);
	open_context_menu(e, [
		{ label: __("Copy"), icon: "copy", action: () => store.copy_field(props.df) },
		{
			label: __("Duplicate"),
			icon: "copy-plus",
			action: () => store.duplicate_field(props.df),
		},
		{
			label: __("Save as snippet"),
			icon: "bookmark-plus",
			action: () => store.prompt_snippet(props.df, "Field"),
		},
		store.clipboard.value && {
			label: __("Paste"),
			icon: "clipboard-paste",
			action: () => store.paste_clipboard(),
		},
		{ divider: true },
		{
			label: __("Delete"),
			icon: "trash",
			danger: true,
			action: () => store.remove_field(props.df),
		},
	]);
}
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
