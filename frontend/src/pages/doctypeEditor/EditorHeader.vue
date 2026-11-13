<!-- The editor's header row: crumbs that end in the layout crumb, the Design | Customize switch,
     Undo and Redo, the menu and Save, and the Editor, Settings and Preview tabs under them. -->
<template>
	<div class="flex w-full flex-col">
		<div class="flex h-12 items-center justify-between gap-3">
			<div class="flex min-w-0 flex-1 items-center gap-2">
				<Breadcrumbs class="-ml-0.5" :items="crumbs" data-crumbs>
					<template #suffix="{ item }">
						<Icon v-if="item.menu" name="lucide-chevron-down" class="ml-0.5 size-4" />
					</template>
				</Breadcrumbs>
				<TabButtons
					v-if="modes.length > 1"
					class="shrink-0"
					:options="modeOptions"
					:model-value="mode"
					data-mode-switch
					@update:model-value="(next: EditorMode) => emit('act', 'editor.set_mode', next)"
				/>
				<Tooltip
					v-if="mode === 'Customize' && appTitle"
					:text="
						__('{0} comes from {1}. Your changes stay on this site.', [
							doctype,
							appTitle,
						])
					"
				>
					<Badge :label="__('From {0}', [appTitle])" theme="gray" class="shrink-0" />
				</Tooltip>
				<NotSavedBadge v-if="dirty" class="shrink-0" />
			</div>
			<div class="hidden shrink-0 items-center lg:flex">
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
import {
	Badge,
	Breadcrumbs,
	Button,
	Dropdown,
	Icon,
	TabButtons,
	TabList,
	Tabs,
	TabTrigger,
	Tooltip,
} from "frappe-ui";
import { __ } from "@/i18n";
import NotSavedBadge from "@/pages/record/NotSavedBadge.vue";
import { canRoute, routeFor } from "@/router/routeFor";
import { EDITOR_TABS } from "./editorActs";
import type { EditorMode } from "./editorSource";
import type { EditorTab } from "./pendingEdits";

const props = defineProps<{
	doctype: string;
	layoutTitle: string;
	dirty: boolean;
	canUndo: boolean;
	canRedo: boolean;
	canSave: boolean;
	saving: boolean;
	mode: EditorMode;
	modes: EditorMode[];
	/** The app the DocType comes from; `null` for a custom DocType. */
	appTitle: string | null;
	developerMode: boolean;
	/** The open child table's crumbs, between the DocType's and the layout's. */
	childCrumbs?: { label: string; onClick?: () => void }[];
}>();
const emit = defineEmits<{ act: [name: string, value?: unknown] }>();
const tab = defineModel<EditorTab>("tab", { required: true });

const modeOptions = computed(() => props.modes.map((mode) => ({ label: __(mode), value: mode })));

const crumbs = computed(() => [
	...(props.mode === "Customize"
		? [{ label: props.doctype, route: listRoute() }, { label: __("Customize") }]
		: [{ label: __("DocType"), route: routeFor("DocType") }, { label: props.doctype }]),
	...(props.childCrumbs ?? []),
	{ label: props.layoutTitle, menu: true, onClick: () => (tab.value = "editor") },
]);

const menu = computed(() => {
	if (props.mode !== "Customize") return [];
	const reset = { label: __("Reset all customizations"), icon: "lucide-rotate-ccw" };
	const exported = { label: __("Export customizations"), icon: "lucide-package" };
	return [
		{ ...reset, onClick: () => emit("act", "customize.reset_all") },
		...(props.developerMode
			? [{ ...exported, onClick: () => emit("act", "customize.export") }]
			: []),
	];
});

// A child table has no list to go back to.
function listRoute() {
	return canRoute(props.doctype) ? routeFor(props.doctype) : undefined;
}
</script>
