<!-- The panel's one list, drawn from `page.panelSections`: a name the Side Panel layout
     carries renders its fields, any other item its component. A label gives a header. -->
<template>
	<div class="panel-layout">
		<!-- A sticky header pins only within its parent: the scrolling group runs to the list's end. -->
		<div
			v-for="group in groups"
			:key="group.pinned ? 'pinned' : 'scrolled'"
			:ref="group.pinned ? setPinned : undefined"
			:class="group.pinned && pinnedClass"
			:data-panel-pinned="group.pinned || undefined"
		>
			<PanelSection
				v-for="entry in group.entries"
				:key="entry.name"
				:name="entry.name"
				:label="entry.label && __(entry.label, null, doctype)"
				:fields="entry.fields"
				:index="entry.index"
				:headerIndex="entry.headerIndex"
				:divided="entry.divided"
				:open="isOpen(entry.name)"
				:pinTop="group.pinned ? 0 : pinHeight"
				@toggle="emit('toggle', entry.name)"
				@expand="emit('expand', $event)"
			>
				<template v-if="entry.actions" #actions>
					<component :is="entry.actions" v-bind="actionBindings(entry)" />
				</template>
				<component :is="entry.component" v-if="entry.component" v-bind="bindings(entry)">
					<template v-if="entry.embedded" #default>
						<component
							:is="entry.embedded.component"
							v-bind="bindings(entry.embedded)"
						/>
					</template>
				</component>
			</PanelSection>
		</div>
		<PanelSectionsSkeleton v-if="loading" />
	</div>
</template>

<script setup lang="ts">
import { computed, inject, provide, ref } from "vue";
import { useFieldTypes, warnMissingCommit } from "@framework/ui/FormLayout";
import { CommitKey, DocKey, ResolveFieldKey, UpdateKey } from "@framework/ui/FormLayout/types";
import type { FieldNode } from "@framework/ui/FormLayout/types";
import { __ } from "@/i18n";
import { BUILTIN, type Surface } from "@/pageEngine/surface";
import type { PanelSectionItem, RecordPageApi } from "@/recordPage";
import PanelSectionsSkeleton from "../skeletons/PanelSectionsSkeleton.vue";
import { PANEL_BUILTINS } from "./builtins";
import PanelSection from "./PanelSection.vue";
import {
	embedQuickActions,
	panelEntries,
	type LayoutSection,
	type PanelEntry,
} from "./panelEntries";
import { usePinnedBlock } from "./pinnedBlock";

const PINNABLE = new Set(PANEL_BUILTINS.map((item) => item.name));

const props = defineProps<{
	surface: Surface<PanelSectionItem>;
	/** The Side Panel layout's sections as they resolve now, by the name a script addresses. */
	sections: LayoutSection[];
	/** The DocType whose translations the headers are looked up in. */
	doctype?: string;
	/** The curated page a script's component mounts with; a built-in injects what it needs. */
	page?: RecordPageApi;
	isOpen: (name: string) => boolean;
	/** The Side Panel layout is still loading: its sections are drawn as skeletons. */
	loading?: boolean;
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
		index,
		headerIndex: entry.label ? headerIndex++ : null,
		divided: index > 0,
	}));
});

// A script that moves, labels or precedes a built-in ends the run, and the rest scrolls.
const groups = computed(() => {
	const lead = numbered.value.findIndex((entry) => !PINNABLE.has(entry.name) || entry.label);
	const split = lead === -1 ? numbered.value.length : lead;
	return [
		{ pinned: true, entries: numbered.value.slice(0, split) },
		{ pinned: false, entries: numbered.value.slice(split) },
	].filter((group) => group.entries.length);
});

const pinned = ref<HTMLElement | null>(null);
const { pinning, height: pinHeight, covering: pinCovering } = usePinnedBlock(pinned);

const pinnedClass = computed(() => [
	pinning.value &&
		"sticky top-0 z-[1] bg-surface-base after:pointer-events-none after:absolute after:inset-x-0 after:top-full after:h-2.5 after:bg-gradient-to-b after:from-surface-base after:to-transparent after:content-['']",
	pinCovering.value ? "after:opacity-100" : "after:opacity-0",
]);

function setPinned(el: unknown) {
	pinned.value = el as HTMLElement | null;
}

function bindings(entry: PanelEntry) {
	return scripted.value.has(entry.name) ? { ...entry.props, page: props.page } : entry.props;
}

// Only a script sets `actions`, so they get the page also on a layout section it updated.
function actionBindings(entry: PanelEntry) {
	return { ...entry.props, page: props.page };
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
