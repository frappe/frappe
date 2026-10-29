<template>
	<DocPanel v-if="tab === 'models'" :spec="SPECS.models" :description="description">
		<template v-if="tabs.length > 1" #tabs>
			<TabButtons v-model="tab" :options="tabs" class="mb-4" />
		</template>
	</DocPanel>
	<DocForm v-else :spec="SPECS.flow_settings" title="Models" :description="description">
		<TabButtons v-model="tab" :options="tabs" class="mb-4" />
	</DocForm>
</template>

<script setup>
import { computed, inject, ref } from "vue";
import { TabButtons } from "frappe-ui";

import DocForm from "./DocForm.vue";
import DocPanel from "./DocPanel.vue";
import { SPECS } from "./specs.js";

defineProps({ description: { type: String, default: "" } });

const page = inject("flowPage");
const tabs = computed(() =>
	[
		{ label: "Models", value: "models" },
		page.can("Flow Settings", "read") ? { label: "Settings", value: "settings" } : null,
	].filter(Boolean)
);
const tab = ref("models");
</script>
