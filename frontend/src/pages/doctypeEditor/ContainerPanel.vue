<!-- The selected tab, section or column: its label and how it draws. The canvas shows every section
     open, so Collapsible and Opened take effect on the record page only. -->
<template>
	<PanelHeader
		:icon="ICONS[selection.kind]"
		:title="title"
		:muted="!node?.label"
		:subtitle="subtitle"
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
		<PanelRow :label="selection.kind === 'section' ? __('Heading') : __('Label')">
			<TextInput
				variant="ghost"
				:model-value="node.label ?? ''"
				:placeholder="selection.kind === 'section' ? __('Add heading…') : __('Add label…')"
				data-panel-container-label
				@change="set('label', ($event.target as HTMLInputElement).value.trim())"
			/>
		</PanelRow>
		<PanelRow v-if="selection.kind === 'section'" :label="__('Columns')" :box="false">
			<div class="flex h-7 items-center pl-2">
				<TabButtons
					:model-value="columnCount"
					:options="COLUMN_COUNTS"
					data-panel-columns
					@update:model-value="setColumns(Number($event))"
				/>
			</div>
		</PanelRow>
		<PanelRow v-if="selection.kind === 'tab'" :label="__('Order')" :box="false">
			<div class="flex h-7 items-center gap-1.5 pl-2" data-panel-order>
				<Button
					variant="subtle"
					size="sm"
					icon="lucide-arrow-left"
					:label="__('Move left')"
					:disabled="tabIndex <= 0"
					@click="moveTab(-1)"
				/>
				<Button
					variant="subtle"
					size="sm"
					icon="lucide-arrow-right"
					:label="__('Move right')"
					:disabled="tabIndex >= canvas.tabs.value.length - 1"
					@click="moveTab(1)"
				/>
			</div>
		</PanelRow>
		<PanelRow v-if="selection.kind === 'section'" :label="__('Description')">
			<Textarea
				variant="ghost"
				:rows="1"
				class="!min-h-7 !resize-none !py-1 [textarea&]:text-base"
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
	<PanelSection
		v-if="node"
		:label="__('Conditions')"
		:count="rules.filter((row) => row.value).length"
	>
		<RuleRow
			v-for="row in rules"
			:key="row.rule.key"
			:label="__(row.rule.label)"
			:value="row.value"
			:summary="words.say(row.value, __(row.rule.empty))"
			:sentence="words.sentence(row.rule, row.value)"
			:subject="node.label || __(UNTITLED[selection.kind])"
			:note="__(row.rule.note)"
			:row-key="`${name}.${row.rule.key}`"
			:codec="words"
			:fields="words.scope.fields"
			:referable="words.referable()"
			:commit="(value: string) => set(row.rule.key, value)"
		/>
	</PanelSection>
	<p
		v-if="selection.kind === 'tab'"
		class="px-4 pt-2 text-p-sm text-ink-gray-5"
		data-panel-tab-hint
	>
		{{
			__(
				"To move a field to this tab, drag it onto the tab's name, or pick the tab in the field's settings."
			)
		}}
	</p>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { Button, Switch, TabButtons, Textarea, TextInput } from "frappe-ui";
import { acts } from "@/acts/dispatcher";
import { __, __n } from "@/i18n";
import type { LayoutTreeSection } from "./layoutTree";
import type { CanvasSelection, DesignCanvas } from "./designCanvas";
import PanelHeader from "./PanelHeader.vue";
import PanelRow from "./PanelRow.vue";
import PanelSection from "./PanelSection.vue";
import { containerRules, ruleValue } from "./ruleRows";
import RuleRow from "./RuleRow.vue";
import { RuleWords } from "./ruleWords";

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
/** "Section · 25 fields", "Tab · 19 sections · 88 fields"; a column is just its kind. */
const subtitle = computed(() => {
	const { kind } = props.selection;
	const kinds = [__(KINDS[kind])];
	const columns = (one: LayoutTreeSection) => one.columns;
	const count = (list: LayoutTreeSection[]) =>
		list.reduce(
			(sum, one) => sum + columns(one).reduce((n, column) => n + column.fields.length, 0),
			0
		);
	if (kind === "section" && section.value) {
		const fields = count([section.value]);
		kinds.push(__n("{0} field", "{0} fields", fields, [fields]));
	} else if (kind === "tab" && node.value && "sections" in node.value) {
		const list = node.value.sections;
		const fields = count(list);
		kinds.push(__n("{0} section", "{0} sections", list.length, [list.length]));
		kinds.push(__n("{0} field", "{0} fields", fields, [fields]));
	}
	return kinds.join(" · ");
});
const columnCount = computed(() => section.value?.columns.length ?? 1);
const tabIndex = computed(() =>
	props.selection.kind === "tab"
		? props.canvas.tabs.value.findIndex(
				(tab) => tab.name === (props.selection as { tab: string }).tab
		  )
		: -1
);
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
	return section.value?.collapsible && !section.value.collapsibleDependsOn
		? [...collapsible, { key: "opened", label: "Opens expanded" }]
		: collapsible;
});
const words = computed(() => RuleWords.of(props.canvas));
const rules = computed(() => {
	const container = node.value;
	if (!container) return [];
	return containerRules(props.selection.kind, container).map((rule) => ({
		rule,
		value: ruleValue(container, rule),
	}));
});
const errors = computed(() =>
	props.selection.kind === "section" ? props.canvas.errorsAt("container", name.value) : []
);
/** An unlabelled first tab reads "Details", as on the strip. */
const title = computed(() => {
	if (node.value?.label) return node.value.label;
	const first =
		props.selection.kind === "tab" && props.canvas.tabs.value[0]?.name === name.value;
	return first ? __("Details") : __(UNTITLED[props.selection.kind]);
});
const removable = computed(() => {
	const { kind } = props.selection;
	if (kind === "tab") return props.canvas.tabs.value.length > 1;
	if (kind === "column") return (section.value?.columns.length ?? 0) > 1;
	return true;
});

const COLUMN_COUNTS = [1, 2, 3].map((count) => ({ label: String(count), value: count }));

/** Adds columns on the right or removes the last ones, one act each so each is an undo step. */
async function setColumns(count: number) {
	const { selection } = props;
	if (selection.kind !== "section") return;
	while (section.value && section.value.columns.length !== count) {
		const { columns } = section.value;
		const before = columns.length;
		if (before < count)
			await acts.perform("canvas.add_column", { section: selection.section });
		else
			await acts.perform("canvas.remove_column", {
				section: selection.section,
				column: columns[before - 1].name,
			});
		if ((section.value?.columns.length ?? before) === before) return;
	}
}

function moveTab(step: number) {
	if (props.selection.kind !== "tab") return;
	void acts.perform("canvas.move_tab", {
		tab: props.selection.tab,
		index: tabIndex.value + step,
	});
}

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
