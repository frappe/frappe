<!--
  A leaf of the consumer's own shape through `#condition`: the tree, the
  conjunction, the nesting and the actions are unchanged, and only what a row
  edits is replaced.
-->
<template>
	<div class="w-full max-w-3xl">
		<ConditionBuilder v-model="conditions" :new-condition="newRule">
			<template #condition="{ condition, update }">
				<div class="flex w-full items-center gap-2">
					<Select
						class="shrink-0"
						:options="ruleTypes"
						:modelValue="condition.ruleType"
						aria-label="Rule"
						@update:modelValue="
							update({
								...condition,
								ruleType: String($event ?? condition.ruleType),
							})
						"
					/>
					<Select
						class="shrink-0"
						:options="courses"
						:modelValue="condition.course"
						aria-label="Course"
						@update:modelValue="update({ ...condition, course: String($event ?? '') })"
					/>
				</div>
			</template>
		</ConditionBuilder>
		<pre class="mt-4 overflow-x-auto text-xs text-ink-gray-6">{{ conditions }}</pre>
	</div>
</template>

<script setup lang="ts">
import { ref } from "vue";
import { Select } from "frappe-ui";
import { ConditionBuilder } from "../index";
import type { ConditionGroup } from "../index";

interface EnrollmentRule {
	ruleType: string;
	course: string;
}

const ruleTypes = ["Enrolled in Course", "Completed Course"];
const courses = [
	{ label: "Introduction to Python", value: "intro-python" },
	{ label: "Advanced TypeScript", value: "advanced-typescript" },
];

const conditions = ref<ConditionGroup<EnrollmentRule>>({
	conjunction: "and",
	conditions: [{ ruleType: "Enrolled in Course", course: "intro-python" }],
});

function newRule(): EnrollmentRule {
	return { ruleType: "Enrolled in Course", course: "" };
}
</script>
