<template>
	<div class="p-6 max-w-3xl">
		<Switch v-model="shown" label="Show errors" class="mb-6" />
		<FormLayout v-model:doc="doc" :layout="layout" />
	</div>
</template>

<script setup lang="ts">
import { computed, provide, reactive, ref } from "vue";
import { Switch } from "frappe-ui";
import FormLayout from "../FormLayout.vue";
import { fieldsToLayout } from "../fieldsToLayout";
import { CommitKey, NO_COMMIT } from "../types";
import { FieldErrorsKey, fieldErrorKey } from "../../Fields/types";
import type { FieldError } from "../../Fields/types";
import type { FieldNode } from "../types";

provide(CommitKey, NO_COMMIT);

const VALUE_FIELDTYPES: [string, string?][] = [
	["Data"],
	["Int"],
	["Long Int"],
	["Float"],
	["Currency"],
	["Percent"],
	["Small Text"],
	["Text"],
	["Long Text"],
	["Code"],
	["JSON"],
	["Markdown Editor"],
	["HTML Editor"],
	["Select", "Open\nClosed"],
	["Check"],
	["Date"],
	["Datetime"],
	["Time"],
	["Duration"],
	["Phone"],
	["Password"],
	["Autocomplete", "Red\nGreen"],
	["Rating"],
	["Link", "User"],
	["Dynamic Link", "link_doctype"],
	["Attach"],
	["Attach Image"],
	["Geolocation"],
	["Color"],
	["Read Only"],
];

const fields: FieldNode[] = [
	...VALUE_FIELDTYPES.map(([fieldtype, options]) => ({
		fieldname: fieldname(fieldtype),
		fieldtype,
		label: fieldtype,
		options,
	})),
	{
		fieldname: "table_multiselect",
		fieldtype: "Table MultiSelect",
		label: "Table MultiSelect",
		childFields: [{ fieldname: "user", fieldtype: "Link", options: "User" }],
	},
	...["items", "read_only_items"].map((tablename) => ({
		fieldname: tablename,
		fieldtype: "Table",
		label: tablename === "items" ? "Table" : "Table (read only)",
		readOnly: tablename !== "items",
		childFields: [
			{ fieldname: "item", fieldtype: "Data", label: "Item" },
			{ fieldname: "qty", fieldtype: "Int", label: "Qty" },
		],
	})),
];

const layout = fieldsToLayout(fields);

const doc = reactive<Record<string, any>>({
	link_doctype: "User",
	items: rows(),
	read_only_items: rows(),
});

const shown = ref(true);

const errors = computed<Record<string, FieldError>>(() => {
	if (!shown.value) return {};
	const all: Record<string, FieldError> = Object.fromEntries(
		fields.map((field) => [field.fieldname, `${field.label} is not valid`])
	);
	all.items = ["Table has a row that is not valid", "Table needs at least three rows"];
	for (const parentfield of ["items", "read_only_items"]) {
		all[fieldErrorKey({ parentfield, key: "name:row-1", fieldname: "qty" })] =
			"Qty must be positive";
	}
	return all;
});
provide(FieldErrorsKey, errors);

function rows() {
	return [
		{ name: "row-1", item: "Pen", qty: -2 },
		{ name: "row-2", item: "Ink", qty: 4 },
	];
}

function fieldname(fieldtype: string): string {
	return fieldtype.toLowerCase().replace(/ /g, "_");
}
</script>
