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
	<div v-else-if="relativeText" class="truncate text-base text-ink-gray-8">
		<Tooltip :text="text">
			<span>{{ relativeText }}</span>
		</Tooltip>
	</div>
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
		/>{{ text }}
	</div>
</template>

<script setup lang="ts">
import { ColorSwatch, DataOpenLink, dataHref } from "@framework/ui/fields";
import type { FieldMeta } from "@framework/ui/fields/types";
import { useFieldDisplay } from "@framework/ui/FormLayout";
import { currentSession } from "@framework/ui/useSession";
import { Checkbox, Rating, Tooltip, dayjs } from "frappe-ui";
import { computed } from "vue";
import { relativeTime } from "@/relativeTime";

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

// The standard stamps and every read-only Datetime (the system writes those) read as "3 days ago";
// an editable Datetime keeps its absolute value.
const STANDARD_STAMPS = new Set(["modified", "creation"]);

const props = defineProps<{ field: FieldMeta; row: Record<string, unknown> }>();

const display = useFieldDisplay();

const value = computed(() => props.row[props.field.fieldname]);
const starCount = computed(() => Number(props.field.options) || 5);
const address = computed(() => {
	const href = dataHref(props.field, value.value);
	return href?.kind === "web" ? href : null;
});

// Stored on the system clock, which the session carries; the person's own zone does not matter.
const relativeText = computed(() => {
	const zone = currentSession()?.timezone;
	if (!zone || !text.value) return "";
	const standard = STANDARD_STAMPS.has(props.field.fieldname);
	if (props.field.fieldtype !== "Datetime" || !(standard || props.field.readOnly)) return "";
	const stamp = dayjs.tz(String(value.value), zone);
	if (!stamp.isValid()) return "";
	return relativeTime(stamp);
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
