<!-- The editor's header row: crumbs that end in the layout crumb, Undo and Redo, the menu and Save,
     and the Editor, Settings and Preview tabs under them. -->
<template>
	<div class="flex w-full flex-col">
		<div class="flex h-12 items-center justify-between gap-3">
			<div class="flex min-w-0 flex-1 items-center gap-2">
				<Breadcrumbs class="-ml-0.5" :items="crumbs" data-crumbs />
				<NotSavedBadge v-if="dirty" class="shrink-0" />
			</div>
			<div class="hidden shrink-0 items-center lg:flex">
				<Tooltip :text="__('Undo')">
					<Button
						variant="ghost"
						icon="lucide-undo-2"
						:label="__('Undo')"
						:disabled="!canUndo"
						@click="emit('act', 'editor.undo')"
					/>
				</Tooltip>
				<Tooltip :text="__('Redo')">
					<Button
						variant="ghost"
						icon="lucide-redo-2"
						:label="__('Redo')"
						:disabled="!canRedo"
						@click="emit('act', 'editor.redo')"
					/>
				</Tooltip>
			</div>
			<Dropdown :options="menu" side="bottom" align="end">
				<Button variant="ghost" icon="lucide-ellipsis" :label="__('More')" />
			</Dropdown>
			<Button variant="solid" :label="__('Save')" disabled />
		</div>
		<Tabs v-model="tab" class="[&_[role='tablist']]:gap-5 [&_[role='tablist']]:py-2">
			<TabList variant="underline">
				<TabTrigger
					v-for="one in TABS"
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
import { Breadcrumbs, Button, Dropdown, TabList, Tabs, TabTrigger, Tooltip } from "frappe-ui";
import { __ } from "@/i18n";
import NotSavedBadge from "@/pages/record/NotSavedBadge.vue";
import { routeFor } from "@/router/routeFor";
import type { EditorTab } from "./pendingEdits";

const props = defineProps<{
	doctype: string;
	layoutTitle: string;
	dirty: boolean;
	canUndo: boolean;
	canRedo: boolean;
	/** The other mode the user may open, if any. */
	switchTo: { label: string; onClick: () => void } | null;
}>();
const emit = defineEmits<{ act: [name: string] }>();
const tab = defineModel<EditorTab>("tab", { required: true });

const TABS: { value: EditorTab; label: string }[] = [
	{ value: "editor", label: "Editor" },
	{ value: "settings", label: "Settings" },
	{ value: "preview", label: "Preview" },
];

const crumbs = computed(() => [
	{ label: __("DocType"), route: routeFor("DocType") },
	{ label: props.doctype },
	{ label: `${props.layoutTitle} ▾`, onClick: () => (tab.value = "editor") },
]);

const menu = computed(() =>
	props.switchTo ? [{ label: props.switchTo.label, onClick: props.switchTo.onClick }] : []
);
</script>
