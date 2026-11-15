<script setup>
import { computed, ref, watch } from "vue";
import { attempt, post } from "../api.js";
import BlockPanel from "./BlockPanel.vue";
import { RECORDS, blank_record, save_record } from "./records.js";
import {
	BLOCK_TYPES,
	WIDGETS,
	move,
	name_key,
	new_block,
	new_section_break,
	new_text,
	set_size,
	to_save,
	with_ids,
} from "./editor.js";

// One layout, edited in place on the grid it is read on. The page draws that grid from what this
// pane exposes, so the tiles stay mounted going in and out of edit mode.
const props = defineProps({
	workspace: { type: Object, required: true },
});

const emit = defineEmits(["saved", "done", "switch", "actions"]);

const frappe = window.frappe;
const __ = window.__;

const blocks = ref(with_ids(props.workspace.content));
const widgets = ref(JSON.parse(JSON.stringify(props.workspace.widgets)));
const touched = ref(new Set());
const selected_id = ref(null);
const previewing = ref(false);
const layouts = props.workspace.layouts || [];
const editing = layouts.find((row) => row.editing);
const initial = JSON.stringify(blocks.value);
const dirty = computed(() => touched.value.size > 0 || JSON.stringify(blocks.value) !== initial);

const selected = computed(() => blocks.value.find((block) => block.id === selected_id.value));
const selected_widget = computed(() => selected.value && widget_of(selected.value));
const form_open = ref(false);

const table_of = (type) => (type === "onboarding" ? "onboardings" : WIDGETS[type]?.table);

// a Widget block's type, with its sizes and title
function widget_type_of(block) {
	if (block.type !== "widget") return null;
	const name = widgets.value.widget?.[block.id]?.type;
	return name && { name, ...props.workspace.widget_types[name] };
}

function widget_of(block) {
	const table = table_of(block.type);
	return table ? widgets.value[table][block.data[name_key(block.type)]] : null;
}

// An onboarding picked here has no steps until the page is saved and loaded again, so they are
// fetched the way the legacy widget fetches them. Onboardings are not saved with the page.
async function load_onboarding(name) {
	const doc = await frappe.model.with_doc("Module Onboarding", name);
	if (!doc) return;
	const steps = await frappe.xcall(
		"frappe.desk.doctype.onboarding_step.onboarding_step.get_onboarding_steps",
		{ ob_steps: doc.steps }
	);
	widgets.value.onboardings[name] = { name, title: __(doc.title), is_complete: 0, steps };
}

watch(
	() =>
		blocks.value
			.filter((block) => block.type === "onboarding")
			.map((block) => block.data.onboarding_name),
	(names) => {
		for (const name of names) {
			if (name && !widgets.value.onboardings[name]) load_onboarding(name);
		}
	},
	{ immediate: true }
);

function on_move(id, target) {
	move(blocks.value, id, target);
}

const TITLES = {
	number_card: __("Number Card"),
	chart: __("Chart"),
	shortcut: __("Shortcut"),
	card: __("Card"),
	quick_list: __("Quick List"),
	onboarding: __("Onboarding"),
	custom_block: __("Custom Block"),
	text: __("Text"),
	spacer: __("Section break"),
};

const ICONS = {
	number_card: "lucide-hash",
	chart: "lucide-chart-column",
	shortcut: "lucide-mouse-pointer-click",
	card: "lucide-square-stack",
	quick_list: "lucide-list",
	onboarding: "lucide-list-checks",
	custom_block: "lucide-code",
	text: "lucide-type",
	spacer: "lucide-separator-horizontal",
};

// A new block goes after the selected one, or last, and is selected.
function insert(block) {
	const at = blocks.value.findIndex((b) => b.id === selected_id.value);
	blocks.value.splice(at === -1 ? blocks.value.length : at + 1, 0, block);
	selected_id.value = block.id;
}

function add_block(type) {
	const { block, widget } = new_block(type, widgets.value, TITLES[type]);
	if (widget) {
		if (RECORDS[type])
			Object.assign(widget, { record: blank_record(type), record_changed: true });
		widgets.value[table_of(type)][widget.label] = widget;
		touched.value.add(block.id);
	}
	insert(block);
}

function add_text() {
	insert(new_text());
}

function add(type) {
	if (type === "text") add_text();
	else if (type === "spacer") insert(new_section_break());
	else add_block(type);
}

function remove() {
	blocks.value = blocks.value.filter((block) => block.id !== selected_id.value);
	selected_id.value = null;
}

async function save() {
	if (!dirty.value) return emit("done");
	try {
		for (const block of blocks.value) {
			const widget = RECORDS[block.type] && widget_of(block);
			if (!widget) continue;
			await save_record(block.type, widget);
			if (block.type === "onboarding") block.data.onboarding_name = widget.name;
		}
		const { blocks: saved, new_widgets } = to_save(blocks.value, widgets.value, touched.value);
		await post("frappe.desk.doctype.workspace.workspace.save_page", {
			name: props.workspace.name,
			public: props.workspace.public ? 1 : 0,
			new_widgets,
			blocks: saved,
			...(props.workspace.layout && { layout: props.workspace.layout }),
		});
		frappe.show_alert({ message: __("Saved"), indicator: "green" });
		emit("done");
	} catch (e) {
		frappe.msgprint(frappe.utils.escape_html(e.message));
	}
}

function discard() {
	frappe.confirm(__("Discard your unsaved changes?"), () => emit("done"));
}

// What saving this layout does, said before the first save freezes anything.
const hint = computed(() => {
	const target = props.workspace.save_target;
	if (target === "private") {
		return {
			icon: "lucide-lock",
			text: __("This workspace is private. Your edits reach only you."),
		};
	}
	if (target === "own") {
		return {
			icon: "lucide-user",
			text: __("Your edits make a layout of your own. Everyone else keeps the shared one."),
		};
	}
	return null;
});

const save_tooltip = computed(() => {
	const target = props.workspace.save_target;
	return target?.includes("/") ? __("Save writes to {0}", [target]) : null;
});

function delete_workspace() {
	frappe.confirm(__("Delete {0}?", [frappe.utils.escape_html(props.workspace.title)]), () =>
		attempt(async () => {
			const message = await post("frappe.desk.doctype.workspace.workspace.delete_page", {
				name: props.workspace.name,
			});
			frappe.ui.update_workspace_pages(message);
			frappe.set_route("/desk");
		})
	);
}

const menu = computed(() => {
	const items = dirty.value
		? [{ label: __("Discard changes"), icon: "lucide-x", onClick: discard }]
		: [];
	if (!props.workspace.public) {
		return [
			...items,
			{ label: __("Delete workspace"), icon: "lucide-trash-2", onClick: delete_workspace },
		];
	}
	return items;
});

// The breadcrumb picker: every layout, strongest first, the one being edited marked.
function picker_actions() {
	if (!layouts.length) return [];
	return layouts.map((row) => ({
		label: row.label,
		section: row.section,
		description: row_description(row),
		icon: row.editing ? "pencil" : row.editable ? undefined : "lock",
		disabled: !row.editable,
		selected: row.editing,
		placement: "breadcrumb",
		group: editing ? `${editing.section} · ${editing.label}` : __("Layouts"),
		onClick: () => switch_to(row),
	}));
}

function row_description(row) {
	const condition = row.is_default
		? __("The page every layout changes")
		: row.condition || __("Everyone");
	return row.editable ? condition : `${condition} · ${__("view only")}`;
}

function switch_to(row) {
	if (row.editing) return;
	if (!dirty.value) return emit("switch", row.name);
	frappe.confirm(__("Discard your unsaved changes?"), () => emit("switch", row.name));
}

watch(
	() => [
		...picker_actions(),
		...(props.workspace.public
			? [
					{
						label: previewing.value ? __("Exit preview") : __("Preview"),
						placement: "toolbar",
						onClick: () => (previewing.value = !previewing.value),
					},
			  ]
			: []),
		...menu.value,
		{ label: __("Save"), placement: "primary", tooltip: save_tooltip.value, onClick: save },
	],
	(actions) => emit("actions", actions),
	{ immediate: true }
);

defineExpose({ blocks, widgets, selected_id, previewing, editing, dirty, on_move, add_text });
</script>

<template>
	<aside
		class="my-4 mr-4 flex min-h-0 w-[21rem] flex-col overflow-hidden rounded-6 border border-outline-gray-2 bg-surface-base"
	>
		<section
			v-if="!form_open"
			class="flex flex-col gap-2 border-outline-gray-2 px-3 pt-4 pb-2"
			:class="{ 'border-b': selected }"
		>
			<div class="flex flex-col gap-1 px-2">
				<span class="text-base font-medium text-ink-gray-8">
					{{ __("Add blocks") }}
				</span>
				<p class="text-p-sm text-ink-gray-5">
					{{ __("Put numbers, charts, links and lists on this page.") }}
					{{
						selected
							? __("New blocks go after the selected one.")
							: __("New blocks go at the end.")
					}}
				</p>
			</div>
			<div class="grid grid-cols-4 gap-1">
				<button
					v-for="type in [...BLOCK_TYPES, 'text', 'spacer']"
					:key="type"
					type="button"
					class="flex w-full flex-col items-center gap-1 rounded-4 px-0.5 py-2 text-ink-gray-6 hover:bg-surface-gray-2 hover:text-ink-gray-8"
					@click="add(type)"
				>
					<span :class="ICONS[type]" class="size-4" aria-hidden="true" />
					<span class="whitespace-nowrap text-2xs">{{ TITLES[type] }}</span>
				</button>
			</div>
		</section>
		<div class="min-h-0 overflow-y-auto">
			<Transition
				mode="out-in"
				enter-active-class="transition duration-200 ease-out motion-reduce:transition-none"
				enter-from-class="translate-y-1 opacity-0"
				leave-active-class="transition duration-100 ease-in motion-reduce:transition-none"
				leave-to-class="opacity-0"
			>
				<BlockPanel
					v-if="selected"
					:key="selected.id"
					:block="selected"
					:widget="selected_widget"
					:title="widget_type_of(selected)?.name"
					:presets="widget_type_of(selected)?.sizes"
					@change="touched.add(selected.id)"
					@resize="
						(preset) => set_size(selected, preset, widget_type_of(selected)?.sizes)
					"
					@remove="remove"
					@close="selected_id = null"
					@form="(open) => (form_open = open)"
				/>
			</Transition>
		</div>
		<section
			v-if="hint"
			class="flex items-start gap-2 border-t border-outline-gray-2 p-5 text-p-sm text-ink-gray-5"
		>
			<span :class="hint.icon" class="mt-0.5 size-4 shrink-0" aria-hidden="true" />
			<span class="min-w-0 [overflow-wrap:anywhere]">{{ hint.text }}</span>
		</section>
	</aside>
</template>
