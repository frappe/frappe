<!--
  Every ConditionBuilder demo on one page, where the interactive behaviour is
  exercised by hand.
-->
<template>
	<div class="flex flex-col gap-10 p-6">
		<section v-for="demo in demos" :key="demo.title" class="flex flex-col gap-3">
			<h3 class="text-lg font-semibold text-ink-gray-8">{{ demo.title }}</h3>
			<p class="text-p-sm text-ink-gray-6">{{ demo.description }}</p>
			<component :is="demo.component" />
		</section>
	</div>
</template>

<script setup lang="ts">
import CustomLeaf from "./CustomLeaf.vue";
import Doctype from "./Doctype.vue";
import FrappeFormat from "./FrappeFormat.vue";
import Minimal from "./Minimal.vue";
import Nested from "./Nested.vue";
import Simple from "./Simple.vue";
import States from "./States.vue";

const demos = [
	{
		title: "Simple",
		description: "One condition, fields supplied by the host.",
		component: Simple,
	},
	{
		title: "From a doctype",
		description: "No fields prop: they come from the doctype's Meta.",
		component: Doctype,
	},
	{
		title: "Nested",
		description: "A group inside a group, each with its own conjunction.",
		component: Nested,
	},
	{
		title: "Frappe format",
		description: "The array a host persists, and a legacy record read back.",
		component: FrappeFormat,
	},
	{
		title: "States",
		description: "Empty, null, read-only, a host-blocked add, every control, raw entries.",
		component: States,
	},
	{
		title: "Minimal",
		description: "Every optional part switched off.",
		component: Minimal,
	},
	{
		title: "Custom leaf",
		description: "A consumer's own leaf shape through #condition.",
		component: CustomLeaf,
	},
];
</script>
