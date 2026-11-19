<!--
  Link and Dynamic Link fields opening the record they name, through a fake `RecordLinkKey`
  host: a plain click is logged below, a modified click opens the fake address in a new tab.
-->
<template>
	<div class="flex max-w-md flex-col gap-5 p-6">
		<LinkField
			v-for="entry in links"
			:key="entry.field.fieldname"
			v-model="doc[entry.field.fieldname]"
			:field="entry.field"
		/>
		<SelectField v-model="doc.reference_doctype" :field="referenceDoctype" />
		<DynamicLinkField v-model="doc.reference_name" :field="referenceName" />
		<pre class="text-xs text-ink-gray-6">opened = {{ opened }}</pre>
	</div>
</template>

<script setup lang="ts">
import { provide, reactive, ref } from "vue";
import LinkField from "../LinkField.vue";
import DynamicLinkField from "../DynamicLinkField.vue";
import SelectField from "../SelectField.vue";
import { DocKey, LinkTitlesKey, RecordLinkKey } from "../types";
import type { FieldMeta } from "../types";

const doc = ref<Record<string, any>>({
	owner: "admin@example.com",
	assigned_to: null,
	modified_by: "admin@example.com",
	route_less: "Guest",
	reference_doctype: "User",
	reference_name: "admin@example.com",
});
const opened = reactive<string[]>([]);

provide(DocKey, doc);
provide(LinkTitlesKey, ref({ "User::admin@example.com": "Administrator" }));
provide(RecordLinkKey, {
	href: (doctype, name) =>
		doctype === "Role" ? null : `/app/${doctype.toLowerCase()}/${encodeURIComponent(name)}`,
	open: (doctype, name) => opened.push(`${doctype} ${name}`),
});

const links: { field: FieldMeta }[] = [
	{
		field: {
			fieldname: "owner",
			fieldtype: "Link",
			label: "Editable, with a value",
			options: "User",
		},
	},
	{ field: { fieldname: "assigned_to", fieldtype: "Link", label: "Empty", options: "User" } },
	{
		field: {
			fieldname: "modified_by",
			fieldtype: "Link",
			label: "Read-only",
			options: "User",
			readOnly: true,
		},
	},
	{
		field: {
			fieldname: "route_less",
			fieldtype: "Link",
			label: "Read-only, no route",
			description: "The fake host has no address for Role.",
			options: "Role",
			readOnly: true,
		},
	},
];

const referenceDoctype: FieldMeta = {
	fieldname: "reference_doctype",
	fieldtype: "Select",
	label: "Reference Type (clear it to drop the Dynamic Link's arrow)",
	options: "\nUser\nRole",
};
const referenceName: FieldMeta = {
	fieldname: "reference_name",
	fieldtype: "Dynamic Link",
	label: "Dynamic Link",
	options: "reference_doctype",
};
</script>
