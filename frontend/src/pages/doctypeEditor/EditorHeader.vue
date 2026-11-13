<!-- The layout crumb stays last: its layout popover hangs on it. -->
<template>
	<div class="flex w-full flex-col">
		<div class="flex h-12 items-center justify-between gap-3">
			<div class="flex min-w-0 flex-1 items-center gap-2">
				<LayoutCrumbs class="-ml-0.5" :crumbs="crumbs" :canvas="canvas" />
				<NotSavedBadge v-if="dirty" class="shrink-0" />
			</div>
			<div class="flex shrink-0 items-center gap-2">
				<TabButtons
					v-if="modes.length > 1"
					:options="modeOptions"
					:model-value="mode"
					data-mode-switch
					@update:model-value="(next) => emit('act', 'editor.set_mode', next as EditorMode)"
				/>
				<div class="hidden items-center lg:flex">
					<Tooltip :text="__('Undo')">
						<Button
							variant="ghost"
							icon="lucide-corner-up-left"
							:label="__('Undo')"
							:disabled="!canUndo"
							@click="emit('act', 'editor.undo')"
						/>
					</Tooltip>
					<Tooltip :text="__('Redo')">
						<Button
							variant="ghost"
							icon="lucide-corner-up-right"
							:label="__('Redo')"
							:disabled="!canRedo"
							@click="emit('act', 'editor.redo')"
						/>
					</Tooltip>
				</div>
			</div>
			<Dropdown v-if="menu.length" :options="menu" side="bottom" align="end">
				<Button variant="ghost" icon="lucide-ellipsis" :label="__('More')" />
			</Dropdown>
			<Button
				variant="solid"
				:label="__('Save')"
				:disabled="!canSave"
				:loading="saving"
				data-editor-save
				@click="emit('act', 'editor.save')"
			/>
		</div>
		<Tabs v-model="tab" class="[&_[role='tablist']]:gap-5 [&_[role='tablist']]:py-2">
			<TabList variant="underline">
				<TabTrigger
					v-for="one in EDITOR_TABS"
					:key="one.value"
					:value="one.value"
					:label="__(one.label)"
				/>
			</TabList>
		</Tabs>
	</div>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { Button, Dropdown, TabButtons, TabList, Tabs, TabTrigger, Tooltip } from "frappe-ui";
import { acts } from "@/acts/dispatcher";
import { __ } from "@/i18n";
import NotSavedBadge from "@/pages/record/NotSavedBadge.vue";
import { canRoute, routeFor } from "@/router/routeFor";
import type { DesignCanvas } from "./designCanvas";
import { EDITOR_TABS } from "./editorActs";
import LayoutCrumbs, { type Crumb } from "./LayoutCrumbs.vue";
import type { EditorMode, EditorTab } from "./pendingEdits";

const props = defineProps<{
	doctype: string;
	/** The canvas the layout crumb opens layouts on; `null` for a new child table, which has none until its first save. */
	canvas: DesignCanvas | null;
	dirty: boolean;
	canUndo: boolean;
	canRedo: boolean;
	canSave: boolean;
	saving: boolean;
	mode: EditorMode;
	modes: EditorMode[];
	/** The app the DocType comes from; `null` for a custom DocType. */
	developerMode: boolean;
	/** The open child table's crumbs, between the DocType's and the layout's. */
	childCrumbs?: { label: string; onClick?: () => void }[];
}>();
const emit = defineEmits<{ act: [name: string, value?: unknown] }>();
const tab = defineModel<EditorTab>("tab", { required: true });

const modeOptions = computed(() => props.modes.map((mode) => ({ label: __(mode), value: mode })));

const crumbs = computed<Crumb[]>(() => {
	const all: Crumb[] = [
		...(props.mode === "Customize"
			? [{ label: props.doctype, route: listRoute() }, { label: __("Customize") }]
			: [{ label: __("DocType"), route: routeFor("DocType") }, { label: props.doctype }]),
		...(props.childCrumbs ?? []),
	];
	const last = all.pop()!;
	const details = () => emit("act", "layouts.open", { type: "Details" });
	return [...all, last.route || last.onClick ? last : { ...last, onClick: details }];
});

// Design's ⋯ offers the Danger zone's Rename and Delete wherever their acts are offered.
const DESIGN_MENU = [
	{ act: "danger.rename_doctype", label: "Rename DocType…", icon: "lucide-pencil" },
	{
		act: "danger.delete_doctype",
		label: "Delete DocType…",
		icon: "lucide-trash-2",
		theme: "red",
	},
];

const menu = computed(() => (props.mode === "Customize" ? customizeMenu() : designMenu()));

function designMenu() {
	return DESIGN_MENU.filter((one) => acts.find(one.act)).map(({ act, label, ...one }) => ({
		...one,
		label: __(label),
		onClick: () => emit("act", act),
	}));
}

function customizeMenu() {
	const reset = { label: __("Reset all customizations"), icon: "lucide-rotate-ccw" };
	const exported = { label: __("Export customizations"), icon: "lucide-package" };
	return [
		{ ...reset, onClick: () => emit("act", "customize.reset_all") },
		...(props.developerMode
			? [{ ...exported, onClick: () => emit("act", "customize.export") }]
			: []),
	];
}

// A child table has no list to go back to.
function listRoute() {
	return canRoute(props.doctype) ? routeFor(props.doctype) : undefined;
}
</script>
