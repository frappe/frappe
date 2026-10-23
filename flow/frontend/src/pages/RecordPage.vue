<template>
	<main class="relative flex min-w-0 flex-1 flex-col bg-surface-base">
		<RecordForm
			v-if="record !== null"
			:key="kind"
			:spec="spec"
			:info="info"
			:name="record || null"
		/>
		<RecordList v-else :key="kind" :spec="spec" :info="info" />
	</main>
</template>

<script setup>
import { computed } from "vue";
import { useRoute } from "vue-router";

import { SPECS } from "../settings/specs.js";
import { PAGES } from "./pages.js";
import RecordForm from "./RecordForm.vue";
import RecordList from "./RecordList.vue";

// A page of records in the chat's place: the list at /<kind>, a record at /<kind>/<name> and a
// blank one at /<kind>/new.
const props = defineProps({ kind: { type: String, required: true } });
const route = useRoute();

const spec = computed(() => SPECS[props.kind]);
const info = computed(() => PAGES.find((page) => page.key === props.kind));
// null for the list, "" for a blank record
const record = computed(() => {
	const name = route.params.record;
	return !name ? null : name === "new" ? "" : name;
});
</script>
