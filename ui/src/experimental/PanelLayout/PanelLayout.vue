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
				:open="openSections[entry.key]"
				@toggle="toggle(entry.key)"
				@expand="emit('expand', $event)"
			>
				<template #header-action>
					<slot name="section-action" :section="entry.section" :index="index" />
				</template>
			</PanelSection>
		</template>
	</div>
</template>

<script setup lang="ts">
import { computed, provide } from "vue";
import PanelSection from "./PanelSection.vue";
import { resolveLayout } from "../../components/FormLayout/resolveLayout";
import { useFieldTypes } from "../../components/FormLayout/useFieldTypes";
import { DocKey, ResolveFieldKey, UpdateKey } from "../../components/FormLayout/types";
import type { FieldNode, Section, Tab } from "../../components/FormLayout/types";
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

// Re-resolves conditional visibility as the user edits, exactly as `FormLayout` does.
const resolvedLayout = computed(() => resolveLayout(props.layout, doc.value));

// The panel holds every field, so every visible tab's sections land in one list.
// A section with no title shows no header, and the ones that do have a title pin
// against each other as if it were not there.
const sections = computed(() => {
	let headerIndex = 0;
	return resolvedLayout.value
		.filter((tab) => !tab.hidden)
		.flatMap((tab) => tab.sections.map((section) => ({ tab, section })))
		.filter((entry) => !entry.section.hidden)
		.map((entry) => ({ ...entry, fields: visibleFields(entry.section) }))
		.filter((entry) => entry.fields.length)
		.map((entry, index) => {
			const title = sectionTitle(entry.section, entry.tab, index);
			return {
				section: entry.section,
				fields: entry.fields,
				title,
				key: entry.section.name ?? entry.section.label ?? "",
				headerIndex: hasHeader(entry.section, index) ? headerIndex++ : null,
			};
		});
});

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

function toggle(key: string) {
	openSections.value = { ...openSections.value, [key]: !openSections.value[key] };
}

function update(fieldname: string, value: any) {
	doc.value[fieldname] = value;
}

const { resolve } = useFieldTypes();

provide(DocKey, doc);
provide(UpdateKey, update);
provide(ResolveFieldKey, resolve);
</script>
