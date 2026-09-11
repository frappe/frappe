<!-- The panel's one list, drawn from `page.panelSections`: a name the Side Panel layout
     carries renders its fields, any other item its component. A label gives a header. -->
<template>
	<div class="panel-layout">
		<template v-for="(entry, index) in numbered" :key="entry.name">
			<PanelSection
				:name="entry.name"
				:label="entry.label"
				:fields="entry.fields"
				:index="index"
				:headerIndex="entry.headerIndex"
				:divided="entry.divided"
				:open="isOpen(entry.name)"
				@toggle="emit('toggle', entry.name)"
				@expand="emit('expand', $event)"
			>
				<component :is="entry.component" v-if="entry.component" v-bind="bindings(entry)">
					<template v-if="entry.embedded" #default>
						<component
							:is="entry.embedded.component"
							v-bind="bindings(entry.embedded)"
						/>
					</template>
				</component>
			</PanelSection>
		</template>
	</div>
</template>

<script setup lang="ts">
import { computed, inject, provide } from "vue";
import { useFieldTypes } from "@framework/ui/components/FormLayout/useFieldTypes";
import {
	CommitKey,
	DocKey,
	ResolveFieldKey,
	UpdateKey,
} from "@framework/ui/components/FormLayout/types";
import { warnMissingCommit } from "@framework/ui/components/FormLayout/warnMissingCommit";
import type { FieldNode } from "@framework/ui/components/FormLayout/types";
import { BUILTIN, type Surface } from "@/recordPage/surface";
import type { PanelSectionItem, RecordPageApi } from "@/recordPage";
import PanelSection from "./PanelSection.vue";
import {
	embedQuickActions,
	panelEntries,
	type LayoutSection,
	type PanelEntry,
} from "./panelEntries";

const props = defineProps<{
	surface: Surface<PanelSectionItem>;
	/** The Side Panel layout's sections as they resolve now, by the name a script addresses. */
	sections: LayoutSection[];
	/** The curated page a script's component mounts with; a built-in injects what it needs. */
	page?: RecordPageApi;
	isOpen: (name: string) => boolean;
}>();

const emit = defineEmits<{ toggle: [name: string]; expand: [field: FieldNode] }>();

const doc = defineModel<Record<string, any>>("doc", { required: true });

const entries = computed(() =>
	embedQuickActions(panelEntries(props.surface.visible(), props.sections))
);

const scripted = computed(
	() =>
		new Set(
			props.surface
				.resolve()
				.filter((entry) => entry.source !== BUILTIN)
				.map((entry) => entry.item.name)
		)
);

// Headers pin against each other as if the headerless were not there. Every item after
// the first draws a divider: a headerless block is still its own section to the eye.
const numbered = computed(() => {
	let headerIndex = 0;
	return entries.value.map((entry, index) => ({
		...entry,
		headerIndex: entry.label ? headerIndex++ : null,
		divided: index > 0,
	}));
});

function bindings(entry: PanelEntry) {
	return scripted.value.has(entry.name) ? { ...entry.props, page: props.page } : entry.props;
}

function update(fieldname: string, value: any) {
	doc.value[fieldname] = value;
}

const { resolve } = useFieldTypes();

warnMissingCommit("PanelLayout", inject(CommitKey, null));

provide(DocKey, doc);
provide(UpdateKey, update);
provide(ResolveFieldKey, resolve);
</script>
