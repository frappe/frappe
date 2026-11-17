<template>
	<DocPanel
		v-if="tab !== 'settings'"
		:key="tab"
		:spec="tab === 'bases' ? SPECS.knowledge_bases : SPECS.knowledge_sources"
		:filters="filters"
		:title="__('Knowledge')"
		:description="DESCRIPTION"
	>
		<template #tabs><TabButtons v-model="tab" :options="tabs" class="mb-4" /></template>
		<template v-if="tab === 'sources'" #filters>
			<!-- the select fills its parent; the wrapper gives it a width -->
			<div class="w-56 max-md:order-last max-md:w-full">
				<FormControl
					v-model="base"
					v-model:query="baseQuery"
					type="combobox"
					:filterable="false"
					:error="error"
					variant="outline"
					:options="baseOptions"
				/>
			</div>
		</template>
	</DocPanel>
	<DocForm v-else :spec="SPECS.knowledge_settings" :title="__('Knowledge')" :description="DESCRIPTION">
		<TabButtons v-model="tab" :options="tabs" class="mb-4" />
	</DocForm>
</template>

<script setup>
import { computed, inject, ref, watch } from "vue";
import { FormControl, TabButtons } from "frappe-ui";

import DocForm from "./DocForm.vue";
import DocPanel from "./DocPanel.vue";
import { searchLinks } from "./links.js";
import { useDebouncedValue } from "@flow/ui-core/debounce.js";
import { __ } from "@flow/ui-core/translate.js";
import { SPECS } from "./specs.js";

const DESCRIPTION = __("Sources agents can search.");

const page = inject("flowPage");
const tabs = computed(() =>
	[
		{ label: __("Bases"), value: "bases" },
		{ label: __("Sources"), value: "sources" },
		page.can("Flow Knowledge Settings", "read")
			? { label: __("Settings"), value: "settings" }
			: null,
	].filter(Boolean)
);
const tab = ref("bases");

const base = ref("");
const baseQuery = ref("");
const query = useDebouncedValue(baseQuery, 300);
const bases = ref([]);
const error = ref("");
watch([tab, query], async ([value, text], _, onCleanup) => {
	let stale = false;
	onCleanup(() => (stale = true));
	if (value !== "sources") return;
	error.value = "";
	try {
		const data = await searchLinks("Flow Knowledge Base", text, "Flow Knowledge Source");
		if (!stale) bases.value = data;
	} catch (err) {
		if (!stale) error.value = err.message;
	}
});
const baseOptions = computed(() => [
	{ label: __("All knowledge bases"), value: "" },
	...bases.value,
	...(base.value && !bases.value.some((option) => option.value === base.value)
		? [{ label: base.value, value: base.value }]
		: []),
]);
const filters = computed(() =>
	tab.value === "sources" && base.value ? { knowledge_base: base.value } : {}
);
</script>
