<!-- A column's cell: the row's value as the record's read-only field shows it. -->
<template>
	<Checkbox v-if="field.fieldtype === 'Check'" :modelValue="Boolean(value)" disabled />
	<Rating
		v-else-if="field.fieldtype === 'Rating'"
		:modelValue="(Number(value) || 0) * starCount"
		:max="starCount"
		:step="0.5"
		disabled
	/>
	<div v-else-if="address" class="flex min-w-0 items-center gap-1">
		<span class="truncate text-base text-ink-gray-8">{{ text }}</span>
		<DataOpenLink :address="address" class="grid shrink-0" />
	</div>
	<div v-else class="truncate text-base text-ink-gray-8">
		<ColorSwatch
			v-if="field.fieldtype === 'Color'"
			:field="field"
			:value="value"
			class="me-1.5"
		/><RecordText v-if="target && text" :doctype="target" :name="String(value)" :text="text" />
		<template v-else>{{ text }}</template>
	</div>
</template>

<script setup lang="ts">
import { ColorSwatch, DataOpenLink, dataHref } from "@framework/ui/fields";
import type { FieldMeta } from "@framework/ui/fields/types";
import { useFieldDisplay } from "@framework/ui/FormLayout";
import { Checkbox, Rating } from "frappe-ui";
import { computed } from "vue";
import RecordText from "./RecordText.vue";

// The form sums these up as "Set" or a first line; a cell shows the stored value.
const STORED_VALUE_FIELDTYPES = new Set([
	"Attach",
	"Attach Image",
	"Image",
	"Geolocation",
	"Code",
	"JSON",
	"Markdown Editor",
	"HTML Editor",
]);

const props = defineProps<{ field: FieldMeta; row: Record<string, unknown> }>();

const display = useFieldDisplay();

const value = computed(() => props.row[props.field.fieldname]);
const starCount = computed(() => Number(props.field.options) || 5);
const address = computed(() => {
	const href = dataHref(props.field, value.value);
	return href?.kind === "web" ? href : null;
});

// A Dynamic Link's doctype is the sibling field its `options` names, which the list reads too.
const target = computed(() => {
	if (props.field.fieldtype === "Link") return props.field.options;
	if (props.field.fieldtype === "Dynamic Link")
		return String(props.row[props.field.options ?? ""] ?? "");
	return "";
});

const text = computed(() => {
	if (value.value == null || value.value === "") return "";
	if (STORED_VALUE_FIELDTYPES.has(props.field.fieldtype)) return String(value.value);
	// The list reads no titles for a Dynamic Link, whose target varies per row; the page's Link titles
	// would name some rows and not others.
	if (props.field.fieldtype === "Dynamic Link") return String(value.value);
	return display(props.field, value.value, { row: props.row });
});
</script>
