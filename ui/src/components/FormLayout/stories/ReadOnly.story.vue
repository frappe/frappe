<!-- Fields the user cannot edit: each draws its formatted value, or keeps its own read view. -->
<template>
	<div class="max-w-3xl p-6">
		<FormLayout v-model:doc="doc" :layout="layout" />
	</div>
</template>

<script setup lang="ts">
import { provide, reactive } from "vue";
import FormLayout from "../FormLayout.vue";
import { fieldsToLayout } from "../fieldsToLayout";
import { CommitKey, NO_COMMIT } from "../types";
import type { FieldNode } from "../types";

provide(CommitKey, NO_COMMIT);

const fields: FieldNode[] = [
	{ fieldname: "iban", fieldtype: "Read Only", label: "Read Only", options: "IBAN" },
	{ fieldname: "data", fieldtype: "Data", label: "Data", readOnly: true },
	{ fieldname: "int", fieldtype: "Int", label: "Int", readOnly: true },
	{ fieldname: "currency", fieldtype: "Currency", label: "Currency", readOnly: true },
	{ fieldname: "date", fieldtype: "Date", label: "Date", readOnly: true },
	{
		fieldname: "status",
		fieldtype: "Select",
		label: "Select",
		options: "Open\nClosed",
		readOnly: true,
	},
	{
		fieldname: "salary",
		fieldtype: "Currency",
		label: "Above the permlevel",
		permlevel: 1,
		permDenied: true,
		readOnly: true,
	},
	{ fieldname: "check", fieldtype: "Check", label: "Check keeps its view", readOnly: true },
	{ fieldname: "code", fieldtype: "Code", label: "Code", options: "JavaScript", readOnly: true },
	{ fieldname: "empty_code", fieldtype: "JSON", label: "Code, empty", readOnly: true },
];

const layout = fieldsToLayout(fields);

const doc = reactive<Record<string, any>>({
	iban: "DE89370400440532013000",
	data: "Ada Lovelace",
	int: 1024,
	currency: 1500.5,
	date: "2026-10-27",
	status: "Closed",
	salary: 92000,
	check: 1,
	code: "const total = items.reduce((sum, i) => sum + i.qty, 0);",
	empty_code: "",
});
</script>
