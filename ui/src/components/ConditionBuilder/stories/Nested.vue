<template>
	<div class="w-full max-w-3xl">
		<ConditionBuilder v-model="conditions" :fields="sampleFields" :max-depth="3" />
		<pre class="mt-4 overflow-x-auto text-xs text-ink-gray-6">{{ conditions }}</pre>
	</div>
</template>

<script setup lang="ts">
import { ref } from "vue";
import { ConditionBuilder } from "../index";
import type { ConditionGroup } from "../index";
import { sampleFields } from "./fields";

const conditions = ref<ConditionGroup>({
	conjunction: "and",
	conditions: [
		{ fieldname: "status", operator: "equals", value: "Open" },
		{
			conjunction: "or",
			conditions: [
				{ fieldname: "priority", operator: "equals", value: "High" },
				{ fieldname: "subject", operator: "like", value: "urgent" },
			],
		},
	],
});
</script>
