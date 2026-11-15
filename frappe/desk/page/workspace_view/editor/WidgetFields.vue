<script setup>
import { computed } from "vue";
import { TextInput } from "frappe-ui";
import { buildLayoutFromMeta, evaluateDependsOn } from "@framework/ui/FormLayout";
import CardLinks from "./CardLinks.vue";
import FieldRows from "./FieldRows.vue";
import InlineFilter from "./InlineFilter.vue";
import { short_filters } from "../widget.js";

// A Widget's label and props, drawn from its Widget Type's fields. A filters prop names the field
// holding the doctype it filters; a container's items are a list of links. Edits write into the
// widget, which the editor watches.
const props = defineProps({
	widget: { type: Object, required: true },
	widget_type: { type: Object, required: true },
});

const __ = window.__;

const config = computed(() => props.widget.config);

const is_filter = (field) => field.fieldtype === "JSON";
const is_items = (field) => field.fieldtype === "Table";

const layout = computed(() =>
	buildLayoutFromMeta(
		props.widget_type.fields
			.filter((field) => !is_filter(field) && !is_items(field))
			.map((field) => ({ ...field, label: __(field.label) })),
		{}
	).map((tab) => ({
		...tab,
		sections: tab.sections.map((section) => ({
			...section,
			columns: [{ fields: section.columns.flatMap((column) => column.fields) }],
		})),
	}))
);

// filters on a doctype the widget has picked, as `[field, operator, value]` rows
const filters = computed(() =>
	props.widget_type.fields.filter(
		(field) =>
			is_filter(field) &&
			field.options &&
			config.value[field.options] &&
			evaluateDependsOn(field.depends_on, config.value)
	)
);

function rows_of(field) {
	const doctype = config.value[field.options];
	return short_filters(config.value[field.fieldname], doctype).map((row) => [doctype, ...row]);
}

function set_filters(field, rows) {
	config.value[field.fieldname] = rows.map((row) => row.slice(1));
}

function set_label(value) {
	props.widget.label = value;
	props.widget.renamed = true;
}
</script>

<template>
	<span class="text-sm text-ink-gray-6">{{ __("Label") }}</span>
	<TextInput
		:aria-label="__('Label')"
		:model-value="widget.label"
		@update:model-value="set_label"
	/>
	<div class="col-span-2">
		<FieldRows :layout="layout" :doc="config" />
	</div>
	<div v-for="field in filters" :key="field.fieldname" class="col-span-2 flex flex-col gap-1.5">
		<span class="text-sm text-ink-gray-6">{{ __(field.label) }}</span>
		<InlineFilter
			:key="config[field.options]"
			:doctype="config[field.options]"
			:filters="rows_of(field)"
			@change="(rows) => set_filters(field, rows)"
		/>
	</div>
	<CardLinks v-if="widget.items" :links="widget.items" />
</template>
