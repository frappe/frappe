<!-- A generated block's rows: a skeleton while its binding loads, then its doctype's tabs as a tab
     strip and its sections as sub-headings, with `depends_on` read from the draft. -->
<template>
	<SettingsRowsSkeleton v-if="state.loading" :rows="skeletonRows" />
	<p v-else-if="state.failed" class="py-3.5 text-base text-ink-red-7">
		{{ __("{0} could not load: {1}", [__(bound.draft.doctype), state.failed]) }}
	</p>
	<template v-else>
		<p
			v-if="state.isNew"
			class="mt-3 rounded-4 bg-surface-gray-2 px-3 py-2 text-base text-ink-gray-6"
		>
			{{ __("No {0} for you yet. The first change creates it.", [__(bound.draft.doctype)]) }}
		</p>
		<div v-if="tabs.length > 1" class="mt-3 w-0 min-w-full overflow-x-auto">
			<TabButtons v-model="tab" :options="tabOptions" />
		</div>
		<template v-for="section in sections" :key="section.name">
			<h4 v-if="section.label" class="mt-5 text-base font-medium text-ink-gray-6">
				{{ __(section.label) }}
			</h4>
			<SettingsFieldRow
				v-for="field in section.columns[0].fields.filter((one) => !one.hidden)"
				:key="field.fieldname"
				:field="field"
				:draft="bound.draft"
				@commit="emit('commit')"
			/>
		</template>
	</template>
</template>

<script setup lang="ts">
import { computed, provide, ref } from "vue";
import { TabButtons } from "frappe-ui";
import {
	getFieldComponent,
	identifyTabs,
	resolveLayout,
	tabStripLabel,
} from "@framework/ui/FormLayout";
import { ResolveFieldKey } from "@framework/ui/FormLayout/types";
import { CommitKey, DocKey, FieldErrorsKey } from "@framework/ui/fields/types";
import { __ } from "@/i18n";
import type { BoundBlock } from "./paneDrafts";
import SettingsFieldRow from "./SettingsFieldRow.vue";
import SettingsRowsSkeleton from "./SettingsRowsSkeleton.vue";

const props = defineProps<{ bound: BoundBlock }>();
const emit = defineEmits<{ commit: [] }>();

const MOST_ROWS = 6;

const state = props.bound.draft.state;

provide(
	DocKey,
	computed(() => state.doc)
);
provide(ResolveFieldKey, getFieldComponent);
// A Table's cells and row dialog write the row in place and report it here, not through `change`.
provide(CommitKey, {
	pending: () => {},
	commit: () => emit("commit"),
	rowChanged: () => emit("commit"),
});
provide(FieldErrorsKey, props.bound.draft.fieldErrors.drawn);

/** As many rows as a field list names, up to `MOST_ROWS`; a whole layout shows three. */
const skeletonRows = Math.min(props.bound.block.fields?.length || 3, MOST_ROWS);

const tabs = computed(() =>
	identifyTabs(resolveLayout(props.bound.layout.value, state.doc).filter((one) => !one.hidden))
);
const tabOptions = computed(() =>
	tabs.value.map((one) => ({
		label: __(tabStripLabel(one.label ?? "", true)),
		value: one.identity,
	}))
);
const picked = ref<string>();
const shownTab = computed(
	() => tabs.value.find((one) => one.identity === picked.value) ?? tabs.value[0]
);
const tab = computed({
	get: () => shownTab.value?.identity,
	set: (identity) => (picked.value = identity),
});
const sections = computed(
	() => shownTab.value?.sections.filter((section) => !section.hidden) ?? []
);
</script>
