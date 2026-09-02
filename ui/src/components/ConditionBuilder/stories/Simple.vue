<template>
	<div class="w-full max-w-3xl">
		<ConditionBuilder v-model="conditions" :fields="sampleFields" />
	</div>
</template>

<script setup lang="ts">
import { ref } from "vue";
import { ConditionBuilder } from "../index";
import type { ConditionGroup } from "../index";
import { sampleFields } from "./fields";

const conditions = ref<ConditionGroup>({
	conjunction: "and",
	conditions: [{ fieldname: "status", operator: "equals", value: "Open" }],
});
</script>
