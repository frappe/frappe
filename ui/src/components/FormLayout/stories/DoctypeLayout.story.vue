<template>
	<div class="p-6 max-w-3xl">
		<div v-if="loading" class="text-ink-gray-6">Loading meta…</div>
		<div v-else-if="error" class="text-ink-red-8">{{ errorMessage }}</div>
		<FormLayout v-else v-model:doc="doc" :layout="layout" />
		<pre class="mt-6 text-xs text-ink-gray-6">doc = {{ doc }}</pre>
	</div>
</template>

<script setup lang="ts">
import { computed, reactive } from "vue";
import FormLayout from "../FormLayout.vue";
import { useDoctypeLayout } from "../useDoctypeLayout";

const props = withDefaults(defineProps<{ doctype?: string }>(), {
	doctype: "ToDo",
});

// Self-contained: the composable is memoised per doctype, so re-mounting this
// panel (e.g. on every tab switch) reuses the cached layout instead of
// re-fetching. The component owns its own doc.
const doc = reactive<Record<string, any>>({});
const { layout, loading, error } = useDoctypeLayout(props.doctype);
const errorMessage = computed(() =>
	error.value instanceof Error ? error.value.message : String(error.value)
);
</script>
