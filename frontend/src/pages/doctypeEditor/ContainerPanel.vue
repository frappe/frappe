<!-- The selected tab, section or column: its label and how it draws. The canvas shows every section
     open, so Collapsible and Opened take effect on the record page only. -->
<template>
	<PanelHeader
		:icon="ICONS[selection.kind]"
		:title="node?.label || __(UNTITLED[selection.kind])"
		:subtitle="__(KINDS[selection.kind])"
		:remove-label="removable ? __(REMOVE[selection.kind]) : undefined"
		@remove="remove"
		@close="acts.perform('canvas.select', null)"
	/>
	<p
		v-for="error in errors"
		:key="error"
		class="px-4 pb-3 text-p-sm text-ink-red-4"
		data-panel-error
	>
		{{ error }}
	</p>
	<PanelSection v-if="node" :label="__(KINDS[selection.kind])">
		<PanelRow :label="__('Label')">
			<TextInput
				variant="ghost"
				:model-value="node.label ?? ''"
				:placeholder="__('None')"
				data-panel-container-label
				@change="set('label', ($event.target as HTMLInputElement).value.trim())"
			/>
		</PanelRow>
		<PanelRow v-if="selection.kind === 'section'" :label="__('Description')">
			<Textarea
				variant="ghost"
				:rows="1"
				class="!min-h-7 !resize-none !py-1"
				:model-value="section?.description ?? ''"
				:placeholder="__('None')"
				@change="set('description', ($event.target as HTMLTextAreaElement).value.trim())"
			/>
		</PanelRow>
		<PanelRow v-for="one in switches" :key="one.key" :label="__(one.label)" :box="false">
			<div class="flex h-7 items-center px-2">
				<Switch
					size="sm"
					:model-value="Boolean(flag(one.key))"
					@update:model-value="set(one.key, $event)"
				/>
			</div>
		</PanelRow>
	</PanelSection>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { Switch, Textarea, TextInput } from "frappe-ui";
import { acts } from "@/acts/dispatcher";
import { __ } from "@/i18n";
import type { LayoutTreeSection } from "./layoutTree";
import type { CanvasSelection, DesignCanvas } from "./designCanvas";
import PanelHeader from "./PanelHeader.vue";
import PanelRow from "./PanelRow.vue";
import PanelSection from "./PanelSection.vue";

type Container = Exclude<CanvasSelection, { kind: "field" }>;

const props = defineProps<{ canvas: DesignCanvas; selection: Container }>();

const ICONS = { tab: "lucide-panel-top", section: "lucide-rows-3", column: "lucide-columns-2" };
const KINDS = { tab: "Tab", section: "Section", column: "Column" };
const UNTITLED = { tab: "Untitled tab", section: "Untitled section", column: "Untitled column" };
const REMOVE = { tab: "Remove tab", section: "Remove section", column: "Remove column" };

const sections = computed(() => props.canvas.tabs.value.flatMap((tab) => tab.sections));
const section = computed<LayoutTreeSection | undefined>(() => {
	const { selection } = props;
	return selection.kind === "tab"
		? undefined
		: sections.value.find((one) => one.name === selection.section);
});
const node = computed(() => {
	const { selection } = props;
	if (selection.kind === "tab")
		return props.canvas.tabs.value.find((tab) => tab.name === selection.tab);
	if (selection.kind === "section") return section.value;
	return section.value?.columns.find((column) => column.name === selection.column);
});
const name = computed(() => {
	const { selection } = props;
	return selection.kind === "tab"
		? selection.tab
		: selection.kind === "column"
		? selection.column
		: selection.section;
});
const switches = computed(() => {
	const { kind } = props.selection;
	if (kind === "tab") return [];
	const hideLabel = { key: "hideLabel", label: "Hide label" };
	if (kind === "column") return [hideLabel];
	const collapsible = [
		hideLabel,
		{ key: "hideBorder", label: "Hide border" },
		{ key: "collapsible", label: "Collapsible" },
	];
	return section.value?.collapsible
		? [...collapsible, { key: "opened", label: "Opens expanded" }]
		: collapsible;
});
const errors = computed(() =>
	props.selection.kind === "section" ? props.canvas.errorsAt("container", name.value) : []
);
const removable = computed(() => {
	const { kind } = props.selection;
	if (kind === "tab") return props.canvas.tabs.value.length > 1;
	if (kind === "column") return (section.value?.columns.length ?? 0) > 1;
	return true;
});

function flag(key: string) {
	return (node.value as unknown as Record<string, unknown> | undefined)?.[key];
}

function set(property: string, value: unknown) {
	if ((flag(property) ?? "") === value || (!flag(property) && !value)) return;
	const { selection } = props;
	const column = selection.kind === "column" ? { section: selection.section } : {};
	void acts.perform("canvas.set_container_property", {
		container: name.value,
		...column,
		property,
		value,
	});
}

function remove() {
	const { selection } = props;
	if (selection.kind === "tab") void acts.perform("canvas.remove_tab", { tab: selection.tab });
	else if (selection.kind === "section")
		void acts.perform("canvas.remove_section", { section: selection.section });
	else
		void acts.perform("canvas.remove_column", {
			section: selection.section,
			column: selection.column,
		});
	void acts.perform("canvas.select", null);
}
</script>
