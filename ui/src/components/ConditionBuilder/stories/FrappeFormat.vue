<!--
  The round trip a host persists: the tree in, Frappe's interleaved array out,
  the array a host compiles into the expression `safe_eval` runs.
-->
<template>
	<div class="w-full max-w-3xl">
		<ConditionBuilder v-model="conditions" :fields="sampleFields" />
		<p class="mt-4 text-xs text-ink-gray-5">Saved to the backend as:</p>
		<pre class="overflow-x-auto text-xs text-ink-gray-6">{{ persisted }}</pre>
		<p class="mt-3 text-xs text-ink-gray-5">Read back from a legacy record:</p>
		<pre class="overflow-x-auto text-xs text-ink-gray-6">{{ legacy }}</pre>
	</div>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";
import { ConditionBuilder, fromFrappeConditions, toFrappeConditions } from "../index";
import type { ConditionGroup } from "../index";
import { sampleFields } from "./fields";

const conditions = ref<ConditionGroup>({
	conjunction: "and",
	conditions: [
		{ fieldname: "status", operator: "equals", value: "Open" },
		{
			conjunction: "and",
			conditions: [{ fieldname: "subject", operator: "like", value: "bug" }],
		},
	],
});

const persisted = computed(() => toFrappeConditions(conditions.value));

// A record stored with Python's own operator tokens, which read back as the
// Filter ids this component stores.
const legacy = computed(() =>
	fromFrappeConditions([["status", "==", "Open"], "and", ["priority", "!=", "Low"]])
);
</script>
