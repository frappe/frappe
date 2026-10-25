<!-- The Text Editor field in each state, with its stored and committed value below it. -->
<template>
	<div class="flex max-w-2xl flex-col gap-8 p-6">
		<div v-for="entry in entries" :key="entry.field.fieldname" class="flex flex-col gap-2">
			<TextEditorField
				v-model="doc[entry.field.fieldname]"
				:field="entry.field"
				:error="entry.error"
				@change="committed[entry.field.fieldname] = $event"
			/>
			<pre class="whitespace-pre-wrap text-xs text-ink-gray-6">
stored = {{ JSON.stringify(doc[entry.field.fieldname]) }}
committed = {{ JSON.stringify(committed[entry.field.fieldname] ?? null) }}</pre
			>
		</div>
	</div>
</template>

<script setup lang="ts">
import { provide, reactive, ref } from "vue";
import TextEditorField from "../TextEditorField.vue";
import { DocKey } from "../types";
import type { FieldError, FieldMeta } from "../types";

const VALUE =
	"<h3>Release plan</h3><p>Ship the <strong>field</strong> first, then the <em>composer</em>.</p><ul><li>Story</li><li>Walk</li></ul>";

const V1_VALUE =
	'<div class="ql-editor read-mode"><p><span style="font-size: 18px;">Large text from desk v1</span></p><p class="ql-indent-1">An indented line</p></div>';

const doc = ref<Record<string, any>>({
	notes: VALUE,
	read_only_notes: VALUE,
	empty_notes: "",
	invalid_notes: "<p>Too short</p>",
	v1_notes: V1_VALUE,
});
const committed = reactive<Record<string, string>>({});

provide(DocKey, doc);

const entries: { field: FieldMeta; error?: FieldError }[] = [
	{ field: { fieldname: "notes", fieldtype: "Text Editor", label: "Editable" } },
	{
		field: {
			fieldname: "read_only_notes",
			fieldtype: "Text Editor",
			label: "Read-only",
			readOnly: true,
		},
	},
	{
		field: {
			fieldname: "empty_notes",
			fieldtype: "Text Editor",
			label: "Empty",
			placeholder: "Write the notes…",
			description: "Clearing the field stores an empty string.",
		},
	},
	{
		field: {
			fieldname: "invalid_notes",
			fieldtype: "Text Editor",
			label: "Error",
			reqd: true,
		},
		error: "Notes must be at least 20 characters",
	},
	{
		field: {
			fieldname: "v1_notes",
			fieldtype: "Text Editor",
			label: "Desk v1 value (edit once to see it normalised)",
			maxHeight: "12rem",
		},
	},
];
</script>
