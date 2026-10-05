<!--
  No `fields` at all: the leaf derives them from the doctype's Meta as `Filter`
  does (FP3), so a Link condition searches its target doctype.
-->
<template>
	<div class="flex w-full max-w-3xl flex-col gap-4">
		<div class="flex items-center gap-2">
			<span class="text-p-sm text-ink-gray-6">Doctype</span>
			<Select v-model="doctype" :options="doctypeOptions" class="w-56" />
		</div>

		<ConditionBuilder :key="doctype" v-model="conditions" :doctype="doctype" />

		<pre class="overflow-x-auto text-xs text-ink-gray-6">{{ conditions }}</pre>
	</div>
</template>

<script setup lang="ts">
import { ref } from "vue";
import { Select } from "frappe-ui";
import { ConditionBuilder } from "../index";
import type { ConditionGroup } from "../index";

// `useDoctypeMeta` reads once at setup, so `:key` remounts the builder on a
// switch rather than leaving it on the previous doctype's fields.
const doctypeOptions = ["ToDo", "User", "Contact"];
const doctype = ref("ToDo");

const conditions = ref<ConditionGroup>({
	conjunction: "and",
	conditions: [{ fieldname: "status", operator: "equals", value: "Open" }],
});
</script>
