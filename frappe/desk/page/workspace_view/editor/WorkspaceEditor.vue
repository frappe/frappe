<script setup>
import { computed, ref } from "vue";
import { Button, Dropdown } from "frappe-ui";
import { post } from "../api.js";
import WorkspaceGrid from "../WorkspaceGrid.vue";
import BlockPanel from "./BlockPanel.vue";
import { DEFAULT_LAYOUT, WIDGETS, move, name_key, set_size, to_save, with_ids } from "./editor.js";

// The default layout, edited in place on the grid it is read on.
const props = defineProps({
	workspace: { type: Object, required: true },
});

const emit = defineEmits(["saved", "done"]);

const frappe = window.frappe;
const __ = window.__;

const blocks = ref(with_ids(props.workspace.content));
const widgets = ref(JSON.parse(JSON.stringify(props.workspace.widgets)));
const touched = ref(new Set());
const selected_id = ref(null);
const saving = ref(false);
const initial = JSON.stringify(blocks.value);
const dirty = computed(() => touched.value.size > 0 || JSON.stringify(blocks.value) !== initial);

const selected = computed(() => blocks.value.find((block) => block.id === selected_id.value));
const selected_widget = computed(() => {
	const spec = WIDGETS[selected.value?.type];
	return spec
		? widgets.value[spec.table][selected.value.data[name_key(selected.value.type)]]
		: null;
});

function on_move(id, target) {
	move(blocks.value, id, target);
}

function remove() {
	blocks.value = blocks.value.filter((block) => block.id !== selected_id.value);
	selected_id.value = null;
}

async function save() {
	saving.value = true;
	try {
		const { blocks: saved, new_widgets } = to_save(blocks.value, widgets.value, touched.value);
		await post("frappe.desk.doctype.workspace.workspace.save_page", {
			name: props.workspace.name,
			public: props.workspace.public ? 1 : 0,
			new_widgets,
			blocks: saved,
			variant: DEFAULT_LAYOUT,
		});
		frappe.show_alert({ message: __("Saved"), indicator: "green" });
		emit("saved");
	} catch (e) {
		frappe.msgprint(frappe.utils.escape_html(e.message));
	} finally {
		saving.value = false;
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

const menu = computed(() =>
	props.workspace.standard
		? [{ label: __("Reset workspace"), icon: "lucide-rotate-ccw", onClick: reset_workspace }]
		: []
);
</script>

<template>
	<div class="flex h-full min-h-0">
		<div class="flex min-w-0 flex-1 flex-col">
			<div
				class="flex items-center justify-end gap-2 border-b border-outline-gray-1 px-4 py-2"
			>
				<Dropdown v-if="menu.length" align="end" :options="menu">
					<Button variant="ghost" icon="lucide-more-horizontal" :label="__('More')" />
				</Dropdown>
				<Button :label="__('Done')" @click="done" />
				<Button variant="solid" :label="__('Save')" :loading="saving" @click="save" />
			</div>
			<div class="min-h-0 flex-1 overflow-y-auto">
				<div class="mx-auto max-w-4xl px-4 pt-4 pb-10">
					<WorkspaceGrid
						:content="blocks"
						:widgets="widgets"
						editing
						:selected="selected_id"
						@select="(block) => (selected_id = block.id)"
						@move="on_move"
					/>
				</div>
			</div>
		</div>
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
	</div>
</template>
