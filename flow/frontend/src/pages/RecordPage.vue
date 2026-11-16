<template>
	<main class="relative flex min-w-0 flex-1 flex-col bg-surface-base">
		<RecordForm :key="kind" :spec="spec" :info="info" :name="record || null" />
	</main>
</template>

<script setup>
import { computed } from "vue";
import { useRoute } from "vue-router";

import { SPECS } from "../settings/specs.js";
import { FORMS } from "./pages.js";
import RecordForm from "./RecordForm.vue";

// A record's form in the chat's place: a record at /<kind>/<name> and a blank one at /<kind>/new.
const props = defineProps({ kind: { type: String, required: true } });
const route = useRoute();

const spec = computed(() => SPECS[props.kind]);
const info = computed(() => FORMS.find((page) => page.key === props.kind));
// "" for a blank record
const record = computed(() => (route.params.record === "new" ? "" : route.params.record));
</script>
