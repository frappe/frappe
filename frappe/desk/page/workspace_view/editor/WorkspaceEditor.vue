<script setup>
import { computed, ref, watch } from "vue";
import { post } from "../api.js";
import BlockPanel from "./BlockPanel.vue";
import {
	BLOCK_TYPES,
	DEFAULT_LAYOUT,
	WIDGETS,
	move,
	name_key,
	new_block,
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
const variant = ref(props.workspace.variant);
const layouts = ref([...(props.workspace.layouts || [])]);
const layout = computed(() => layouts.value.find((l) => l.role === variant.value));
const initial = JSON.stringify(blocks.value);
const dirty = computed(
	() =>
		layout.value?.source === "New" ||
		touched.value.size > 0 ||
		JSON.stringify(blocks.value) !== initial
);

const selected = computed(() => blocks.value.find((block) => block.id === selected_id.value));
const selected_widget = computed(() => {
	const spec = WIDGETS[selected.value?.type];
	return spec
		? widgets.value[spec.table][selected.value.data[name_key(selected.value.type)]]
		: null;
});

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
	}
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
		widgets.value[WIDGETS[type].table][widget.label] = widget;
		touched.value.add(block.id);
	}
	insert(block);
}

function add_text() {
	insert(new_text());
}

function remove() {
	blocks.value = blocks.value.filter((block) => block.id !== selected_id.value);
	selected_id.value = null;
}

async function save() {
	try {
		const { blocks: saved, new_widgets } = to_save(blocks.value, widgets.value, touched.value);
		await post("frappe.desk.doctype.workspace.workspace.save_page", {
			name: props.workspace.name,
			public: props.workspace.public ? 1 : 0,
			new_widgets,
			blocks: saved,
			variant: variant.value || DEFAULT_LAYOUT,
		});
		frappe.show_alert({ message: __("Saved"), indicator: "green" });
		emit("saved", variant.value);
	} catch (e) {
		frappe.msgprint(frappe.utils.escape_html(e.message));
	}
}

function done() {
	if (!dirty.value) return emit("done");
	frappe.confirm(__("Discard your unsaved changes?"), () => emit("done"));
}

function reset_workspace() {
	frappe.confirm(
		__("Reset {0} to the app's version? This removes every change this site made to it.", [
			frappe.utils.escape_html(props.workspace.title),
		]),
		async () => {
			await post(
				"frappe.desk.doctype.custom_workspace.custom_workspace.reset_workspace_customization",
				{ workspace: props.workspace.name }
			);
			emit("saved");
		}
	);
}

const layout_label = (l) => (l.role ? __(l.role) : __("Default"));

function layout_actions() {
	if (!layouts.value.length) return [];
	const group = `${layout_label(layout.value || {})} · ${__(layout.value?.source || "New")}`;
	return [
		...layouts.value.map((l) => ({
			label: `${layout_label(l)} · ${__(l.source)}`,
			placement: "breadcrumb",
			group,
			onClick: () => switch_to(l.role),
		})),
		{
			label: __("New layout for a role"),
			placement: "breadcrumb",
			group,
			onClick: new_layout,
		},
	];
}

function switch_to(role) {
	if (role === variant.value) return;
	if (!dirty.value) return emit("switch", role);
	frappe.confirm(__("Discard your unsaved changes?"), () => emit("switch", role));
}

// A new layout starts as a whole copy of the one on screen, and exists once it is saved.
function new_layout() {
	const taken = [...layouts.value.map((l) => l.role).filter(Boolean)];
	frappe.prompt(
		{
			fieldname: "role",
			fieldtype: "Link",
			options: "Role",
			label: __("Role"),
			reqd: 1,
			get_query: () => ({
				filters: {
					name: ["not in", [...taken, "Guest", "All", "Desk User", "Administrator"]],
					desk_access: 1,
				},
			}),
		},
		({ role }) => {
			layouts.value.push({ role, source: "New" });
			variant.value = role;
			for (const block of blocks.value) {
				if (WIDGETS[block.type]) touched.value.add(block.id);
			}
		},
		__("New layout for a role"),
		__("Create")
	);
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
	if (target && target.includes("/")) {
		return { icon: "lucide-file-code", text: __("Save writes to {0}", [target]) };
	}
	if (target === "site copy" && !["Site copy", "Site", "New"].includes(layout.value?.source)) {
		return {
			icon: "lucide-triangle-alert",
			text: __(
				"Saving makes a site copy of this layout. It stops getting updates from {0}.",
				[layout.value?.source]
			),
		};
	}
	return null;
});

function reset_layout() {
	frappe.confirm(
		__("Bring back the app's {0} layout?", [layout_label(layout.value)]),
		async () => {
			await post(
				"frappe.desk.doctype.custom_workspace.custom_workspace.reset_workspace_customization",
				{ workspace: props.workspace.name, variant: variant.value || DEFAULT_LAYOUT }
			);
			emit("saved", variant.value);
		}
	);
}

function delete_layout() {
	frappe.confirm(__("Delete the {0} layout?", [layout_label(layout.value)]), async () => {
		await post(
			"frappe.desk.doctype.custom_workspace.custom_workspace.delete_workspace_layout",
			{
				workspace: props.workspace.name,
				variant: variant.value,
			}
		);
		emit("switch", null);
	});
}

function delete_workspace() {
	frappe.confirm(
		__("Delete {0}?", [frappe.utils.escape_html(props.workspace.title)]),
		async () => {
			await post("frappe.desk.doctype.workspace.workspace.delete_page", {
				name: props.workspace.name,
			});
			frappe.set_route("/desk");
		}
	);
}

const menu = computed(() => {
	if (!props.workspace.public) {
		return [
			{ label: __("Delete workspace"), icon: "lucide-trash-2", onClick: delete_workspace },
		];
	}
	const items = [];
	if (layout.value?.source === "Site copy") {
		items.push({
			label: __("Reset this layout"),
			icon: "lucide-undo-2",
			onClick: reset_layout,
		});
	}
	if (layout.value?.source === "Site" && variant.value) {
		items.push({ label: __("Delete layout"), icon: "lucide-trash-2", onClick: delete_layout });
	}
	if (props.workspace.standard) {
		items.push({
			label: __("Reset workspace"),
			icon: "lucide-rotate-ccw",
			onClick: reset_workspace,
		});
	}
	return items;
});

watch(
	() => [
		...layout_actions(),
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
		{ label: __("Done"), placement: "secondary", onClick: done },
		{ label: __("Save"), placement: "primary", onClick: save },
	],
	(actions) => emit("actions", actions),
	{ immediate: true }
);

defineExpose({ blocks, widgets, selected_id, previewing, variant, on_move, add_text });
</script>

<template>
	<aside
		class="my-4 mr-4 flex min-h-0 w-[21rem] flex-col overflow-hidden rounded-6 border border-outline-gray-2 bg-surface-base"
	>
		<section class="flex flex-col gap-2 border-b border-outline-gray-2 px-3 pt-4 pb-2">
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
					v-for="type in [...BLOCK_TYPES, 'text']"
					:key="type"
					type="button"
					class="flex w-full flex-col items-center gap-1 rounded-4 px-0.5 py-2 text-ink-gray-6 hover:bg-surface-gray-2 hover:text-ink-gray-8"
					@click="type === 'text' ? add_text() : add_block(type)"
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
					@change="touched.add(selected.id)"
					@resize="(preset) => set_size(selected, preset)"
					@remove="remove"
					@close="selected_id = null"
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
