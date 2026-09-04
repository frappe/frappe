<!--
  Everything optional switched off for a panel that supplies its own frame and
  controls: no card, no "Where", no overflow menu, no add affordance.
-->
<template>
	<div class="w-full max-w-3xl">
		<ConditionBuilder
			v-model="conditions"
			:fields="sampleFields"
			bordered="none"
			:columns="{ operator: 'minmax(0, 9rem)' }"
		>
			<!-- A node that draws nothing, not an empty template: an empty one
			     produces no vnode, and Vue then renders the slot's fallback. -->
			<template #condition-where><span /></template>
			<template #condition-conjunction><span /></template>
			<template #condition-actions><span /></template>
			<template #add-condition><span /></template>
		</ConditionBuilder>
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
		{ fieldname: "subject", operator: "like", value: "refund" },
	],
});
</script>
