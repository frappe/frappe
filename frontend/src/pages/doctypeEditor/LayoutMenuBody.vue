<!-- The layout menu's rows: each layout type with its source and conditional layouts, then the open
     layout's acts and "Add a layout…". -->
<template>
	<div class="flex w-80 flex-col divide-y divide-outline-gray-1" data-layout-menu>
		<div class="flex flex-col gap-px p-1.5">
			<template v-for="type in menu.types" :key="type.type">
				<LayoutMenuRow
					:icon="type.icon"
					:name="type.label"
					:badge="type.badge"
					:open="type.open"
					:data-layout-row="type.type"
					@click="pick(type.ref)"
				/>
				<LayoutMenuRow
					v-for="layout in type.layouts"
					:key="layout.ref.id"
					indented
					:name="layout.name"
					:badge="layout.badge"
					:open="layout.open"
					:data-layout-row="`${type.type}/${layout.ref.id}`"
					@click="pick(layout.ref)"
				/>
			</template>
			<p
				v-if="menu.note"
				class="px-2 pb-1 pt-1.5 text-p-sm text-ink-gray-5"
				data-layout-note
			>
				{{ menu.note }}
			</p>
		</div>
		<div
			v-if="canvas.editable && menu.open"
			class="flex flex-col gap-px p-1.5"
			data-layout-acts
		>
			<div class="px-2 pb-1.5 pt-1">
				<p class="truncate text-sm-medium text-ink-gray-5" :title="menu.open.name">
					{{ menu.open.name }}
				</p>
				<p class="mt-1 text-sm text-ink-gray-4">{{ menu.open.where }}</p>
			</div>
			<LayoutMenuRow
				v-for="act in menu.open.acts"
				:key="act"
				:icon="ACTS[act].icon"
				:name="ACTS[act].label()"
				:data-layout-act="act"
				@click="run(act)"
			/>
		</div>
		<div v-if="canvas.editable" class="flex flex-col p-1.5">
			<LayoutMenuRow
				icon="lucide-plus"
				:name="__('Add a layout…')"
				data-layout-add
				@click="add"
			/>
		</div>
	</div>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { acts } from "@/acts/dispatcher";
import { __ } from "@/i18n";
import type { DesignCanvas } from "./designCanvas";
import { addLayout, runOpenLayoutAct } from "./layoutDialogs";
import { layoutMenu, resetWording, type OpenLayoutAct } from "./layoutMenu";
import LayoutMenuRow from "./LayoutMenuRow.vue";
import type { LayoutRef } from "./workingLayouts";

const props = defineProps<{ canvas: DesignCanvas }>();
const emit = defineEmits<{ close: [] }>();

const menu = computed(() => layoutMenu(props.canvas.working.value, props.canvas.openLayout.value));

const ACTS: Record<OpenLayoutAct, { label: () => string; icon: string }> = {
	edit_condition: { label: () => __("Edit condition…"), icon: "lucide-filter" },
	rename: { label: () => __("Rename…"), icon: "lucide-pencil" },
	reset_to_app: {
		label: () =>
			resetWording(props.canvas.working.value, props.canvas.openLayout.value.type).actLabel,
		icon: "lucide-rotate-ccw",
	},
	delete: { label: () => __("Delete layout"), icon: "lucide-trash-2" },
};

function pick(layout: LayoutRef) {
	emit("close");
	void acts.perform("layouts.open", layout);
}

// Each act closes the menu first: it may open a dialog or change the canvas under it.
function run(act: OpenLayoutAct) {
	emit("close");
	void runOpenLayoutAct(props.canvas, act);
}

function add() {
	emit("close");
	void addLayout(props.canvas, menu.value);
}
</script>
