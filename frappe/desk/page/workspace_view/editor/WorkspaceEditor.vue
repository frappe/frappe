<script setup>
import { computed, reactive, ref, watch } from "vue";
import { attempt, get, post } from "../api.js";
import BlockPanel from "./BlockPanel.vue";
import PaneSettings from "./PaneSettings.vue";
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

const emit = defineEmits(["saved", "done", "switch", "new-layout", "created", "actions"]);

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
// a new layout or a new page is unsaved from the start, and nothing exists until Save
const is_draft = props.workspace.draft || props.workspace.new_layout;
const page_settings = reactive({ ...props.workspace.page_settings });
const layout_settings = reactive({
	layout_name: "",
	condition: "",
	module: "",
	...props.workspace.layout_settings,
});
const settings_changed = ref(false);
const dirty = computed(
	() =>
		is_draft ||
		settings_changed.value ||
		touched.value.size > 0 ||
		JSON.stringify(blocks.value) !== initial
);

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
		const name = props.workspace.draft ? await create_page() : props.workspace.name;
		await post("frappe.desk.doctype.workspace.workspace.save_page", {
			name,
			public: props.workspace.public ? 1 : 0,
			new_widgets,
			blocks: saved,
			...(props.workspace.layout && { layout: props.workspace.layout }),
			...(props.workspace.layout_fields?.length && { layout_settings }),
			...(settings_changed.value && !props.workspace.draft && { page_settings }),
			...(props.workspace.view_as && { view_as: props.workspace.view_as }),
		});
		frappe.show_alert({ message: __("Saved"), indicator: "green" });
		if (props.workspace.draft) emit("created", name);
		else emit("done");
	} catch (e) {
		frappe.msgprint(frappe.utils.escape_html(e.message));
	}
}

async function create_page() {
	const title = window.strip_html(page_settings.title || "").trim();
	if (!title) throw new Error(__("Give the workspace a title."));
	const is_public = props.workspace.public;
	const name = is_public ? title : `${title}-${frappe.session.user}`;
	const message = await post("frappe.desk.doctype.workspace.workspace.new_page", {
		new_page: {
			name,
			label: name,
			title,
			icon: page_settings.icon,
			module: page_settings.module,
			public: is_public ? 1 : 0,
			for_user: is_public ? "" : frappe.session.user,
			content: "[]",
		},
	});
	frappe.ui.update_workspace_pages(message);
	return name;
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

function picker_actions() {
	if (!layouts.length) return [];
	const rows = layouts.map((row) => ({
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
	const new_row = {
		label: __("New layout"),
		icon: "plus",
		placement: "breadcrumb",
		group: rows[0].group,
		onClick: () =>
			dirty.value ? confirm_discard(() => emit("new-layout")) : emit("new-layout"),
	};
	return props.workspace.new_layout
		? rows.map((row) => ({ ...row, group: __("New layout") }))
		: [...rows, new_row];
}

function view_as_user(user) {
	const open = () =>
		attempt(async () => {
			if (!user) return emit("switch", undefined, {});
			const { layout } = await get("frappe.desk.desktop.view_as", {
				workspace: props.workspace.name,
				user,
			});
			emit("switch", layout || undefined, { view_as: user });
		});
	dirty.value ? confirm_discard(open) : open();
}

function reset_layout() {
	frappe.confirm(__("Undo every change this layout makes to the page?"), () =>
		attempt(async () => {
			await post("frappe.desk.doctype.workspace.workspace.reset_layout", {
				workspace: props.workspace.name,
				...(props.workspace.layout && { layout: props.workspace.layout }),
			});
			emit("switch", props.workspace.layout || undefined, viewer());
		})
	);
}

function delete_layout() {
	frappe.confirm(__("Delete the {0} layout?", [layout_settings.layout_name]), () =>
		attempt(async () => {
			await post("frappe.desk.doctype.workspace.workspace.delete_layout", {
				workspace: props.workspace.name,
				layout: props.workspace.layout,
			});
			emit("switch", undefined, viewer());
		})
	);
}

function reset_field(field) {
	attempt(async () => {
		await post("frappe.desk.doctype.custom_workspace.custom_workspace.reset_page_fields", {
			workspace: props.workspace.name,
			fields: [field],
		});
		emit("switch", props.workspace.layout || undefined, viewer());
	});
}

const viewer = () => (props.workspace.view_as ? { view_as: props.workspace.view_as } : {});

// on every editable layout but the default, once it changes something
const can_reset = computed(() =>
	props.workspace.can_edit
		? Boolean(props.workspace.layout_settings && props.workspace.has_changes)
		: props.workspace.own_layout
);

function confirm_discard(then) {
	frappe.confirm(__("Discard your unsaved changes?"), then);
}

function row_description(row) {
	const condition = row.is_default
		? __("The page every layout changes")
		: row.condition || __("Everyone");
	return row.editable ? condition : `${condition} · ${__("view only")}`;
}

function switch_to(row) {
	if (row.editing) return;
	const viewer = props.workspace.view_as ? { view_as: props.workspace.view_as } : {};
	if (!dirty.value) return emit("switch", row.name, viewer);
	confirm_discard(() => emit("switch", row.name, viewer));
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
		...(can_reset.value
			? [
					{
						label: __("Reset"),
						icon: "undo-2",
						placement: "secondary",
						onClick: reset_layout,
					},
			  ]
			: []),
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
			<PaneSettings
				v-if="!selected && !form_open"
				:page="page_settings"
				:page_fields="workspace.page_fields"
				:layout="layout_settings"
				:layout_fields="workspace.layout_fields"
				:view_as="workspace.view_as"
				:can_view_as="layouts.length > 0 && !is_draft"
				@change="settings_changed = true"
				@view-as="view_as_user"
				:can_delete_layout="Boolean(workspace.layout && workspace.layout_fields?.length)"
				:overrides="workspace.page_overrides"
				:owner_title="workspace.owner_title"
				@delete-layout="delete_layout"
				@reset-field="reset_field"
			/>
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
