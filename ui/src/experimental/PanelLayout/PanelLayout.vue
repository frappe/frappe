<!-- A dense one-column read of every field: label left, value right, click to edit.
     The sibling of `FormLayout` over the same layout resolver. -->
<template>
	<div class="panel-layout">
		<template v-for="(entry, index) in sections" :key="entry.key">
			<PanelSection
				:section="entry.section"
				:title="entry.title"
				:fields="entry.fields"
				:index="index"
				:headerIndex="entry.headerIndex"
				:open="openSections[entry.key] ?? entry.defaultOpen"
				@toggle="toggle(entry)"
				@expand="emit('expand', $event)"
			>
				<template #header-action>
					<slot name="section-action" :section="entry.section" :index="index" />
				</template>
				<component :is="entry.component" v-if="entry.component" v-bind="entry.props" />
			</PanelSection>
		</template>
	</div>
</template>

<script setup lang="ts">
import { computed, provide } from "vue";
import PanelSection from "./PanelSection.vue";
import { sectionName } from "./sectionName";
import { resolveLayout } from "../../components/FormLayout/resolveLayout";
import { useFieldTypes } from "../../components/FormLayout/useFieldTypes";
import { DocKey, ResolveFieldKey, UpdateKey } from "../../components/FormLayout/types";
import type { FieldNode, Section, Tab } from "../../components/FormLayout/types";
import type { PanelSectionItem } from "../RecordPage/types";
import type { PanelLayoutProps } from "./types";

const props = defineProps<PanelLayoutProps>();

/** A fieldtype with no honest row was clicked; the host opens it in the full form. */
const emit = defineEmits<{ expand: [field: FieldNode] }>();

const doc = defineModel<Record<string, any>>("doc", { required: true });

// Fully controlled: the effective open state of every section, by section name.
// A key the map does not carry is closed; the host resolves the layout's defaults.
const openSections = defineModel<Record<string, boolean>>("openSections", {
	default: () => ({}),
});

type PanelEntry = {
	section: Section;
	fields: FieldNode[];
	title: string;
	key: string;
	component?: any;
	props?: Record<string, any>;
	defaultOpen?: boolean;
};

// Re-resolves conditional visibility as the user edits, exactly as `FormLayout` does.
const resolvedLayout = computed(() => resolveLayout(props.layout, doc.value));

// Scripts see the layout as it resolves now: a hide is an overlay on top of
// `dependsOn`, never an override of it, and a scripted section is a
// component-backed splice that is never written into the layout itself.
props.surface?.provideBuiltins(() =>
	flatEntries().map((entry) => ({ name: entry.key, label: entry.title })),
);

const sections = computed(() => numbered(props.surface ? overlaid() : flatEntries()));

// The panel holds every field, so every visible tab's sections land in one list.
function flatEntries(): PanelEntry[] {
	return resolvedLayout.value
		.filter((tab) => !tab.hidden)
		.flatMap((tab) => tab.sections.map((section) => ({ tab, section })))
		.filter((entry) => !entry.section.hidden)
		.map((entry) => ({ ...entry, fields: visibleFields(entry.section) }))
		.filter((entry) => entry.fields.length)
		.map((entry, index) => ({
			section: entry.section,
			fields: entry.fields,
			title: sectionTitle(entry.section, entry.tab, index),
			key: sectionName(entry.section),
		}));
}

function overlaid(): PanelEntry[] {
	const entries = new Map(flatEntries().map((entry) => [entry.key, entry]));
	return props.surface!.visible().map((item) => entries.get(item.name) ?? scripted(item));
}

function scripted(item: PanelSectionItem): PanelEntry {
	return {
		section: { name: item.name, label: item.label, columns: [] } as any,
		fields: [],
		title: item.label ?? "",
		key: item.name,
		component: item.component,
		props: { ...(item.props ?? {}), page: props.page },
		defaultOpen: item.opened !== false,
	};
}

// A section with no title shows no header, and the ones that do have a title pin
// against each other as if it were not there.
function numbered(entries: PanelEntry[]) {
	let headerIndex = 0;
	return entries.map((entry, index) => ({
		...entry,
		headerIndex: hasHeader(entry.section, index) ? headerIndex++ : null,
	}));
}

// The panel is always one column, so a section's columns flatten into one list.
function visibleFields(section: Section) {
	return section.columns.flatMap((column) => column.fields).filter((field) => !field.hidden);
}

// The panel opens on a header, so the first section borrows a title where it has none.
function sectionTitle(section: Section, tab: Tab, index: number) {
	if (section.label) return section.label;
	return index === 0 ? tab.label || "Details" : "";
}

function hasHeader(section: Section, index: number) {
	if (index === 0) return true;
	return Boolean(section.label) && !section.hideLabel;
}

function toggle(entry: PanelEntry) {
	const open = openSections.value[entry.key] ?? entry.defaultOpen;
	openSections.value = { ...openSections.value, [entry.key]: !open };
}

function update(fieldname: string, value: any) {
	doc.value[fieldname] = value;
}

const { resolve } = useFieldTypes();

provide(DocKey, doc);
provide(UpdateKey, update);
provide(ResolveFieldKey, resolve);
</script>
