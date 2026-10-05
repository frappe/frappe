<!--
  Every state the builder survives: empty and `null` models, read-only, an add
  control the host has blocked, every value control, and a condition on a field
  the doctype no longer has.
-->
<template>
	<div class="grid w-full max-w-3xl gap-8">
		<section v-for="c in cases" :key="c.title" class="grid gap-2">
			<h4 class="font-mono text-xs uppercase tracking-wide text-ink-gray-5">
				{{ c.title }}
			</h4>
			<ConditionBuilder v-model="c.model.value" :fields="sampleFields" v-bind="c.props" />
		</section>

		<section class="grid gap-2">
			<h4 class="font-mono text-xs uppercase tracking-wide text-ink-gray-5">
				Adding blocked by the host
			</h4>
			<ConditionBuilder v-model="hostBlockedAdd" :fields="sampleFields">
				<template #add-condition>
					<Button label="Add Condition" icon-left="lucide-plus" disabled />
				</template>
			</ConditionBuilder>
		</section>
	</div>
</template>

<script setup lang="ts">
import { ref } from "vue";
import { Button } from "frappe-ui";
import { ConditionBuilder, fromFrappeConditions } from "../index";
import type { ConditionGroup } from "../index";
import { sampleFields } from "./fields";

const filled: ConditionGroup = {
	conjunction: "and",
	conditions: [{ fieldname: "status", operator: "equals", value: "Open" }],
};

const empty = ref<ConditionGroup>({ conjunction: "and", conditions: [] });
const nullish = ref<ConditionGroup | null>(null);
const readonlyTree = ref<ConditionGroup>(structuredClone(filled));

// There is no prop for "editable but not extendable" any more: the host renders
// the add control it wants through `#addCondition` and disables that.
const hostBlockedAdd = ref<ConditionGroup>(structuredClone(filled));

// Handles and move items are opt-in: `reorderable` is off by default.
const fixedOrder = ref<ConditionGroup>({
	conjunction: "and",
	conditions: [
		{ fieldname: "status", operator: "equals", value: "Open" },
		{ fieldname: "subject", operator: "like", value: "urgent" },
	],
});

// Every value control the dispatch can pick, so each one renders.
const allTypes = ref<ConditionGroup>({
	conjunction: "and",
	conditions: [
		{ fieldname: "subject", operator: "like", value: "urgent" },
		{ fieldname: "creation", operator: "between", value: "" },
		{ fieldname: "rating", operator: ">=", value: 3 },
		{ fieldname: "resolved", operator: "equals", value: "Yes" },
		{ fieldname: "status", operator: "is", value: "set" },
		{ fieldname: "owner", operator: "in", value: [] },
		{ fieldname: "_assign", operator: "like", value: "john" },
	],
});

// A stored condition naming a field that is not in `fields` at all: a field the
// rule has outlived. The row stays readable and its picker stays live; an entry
// the parser cannot model as a leaf at all is dropped on read, so there is none
// to show here.
const deletedField = ref<ConditionGroup>(
	fromFrappeConditions([["deleted_field", "equals", "Open"]])
);

const cases = [
	{ title: "Empty", model: empty, props: {} },
	{ title: "modelValue = null", model: nullish, props: {} },
	{ title: "Read-only", model: readonlyTree, props: { readonly: true } },
	{
		title: "Reorderable",
		model: fixedOrder,
		props: { reorderable: true },
	},
	{ title: "Every value control", model: allTypes, props: {} },
	{ title: "Condition on a deleted field", model: deletedField, props: {} },
];
</script>
