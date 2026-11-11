<script setup>
import { computed, onMounted, reactive, watch } from "vue";
import { buildLayoutFromMeta } from "@framework/ui/FormLayout";
import FieldRows from "./FieldRows.vue";
import InlineFilter from "./InlineFilter.vue";
import { filter_rows } from "../filters.js";

// A doctype's record keeps filter rows. A report or a custom source keeps the values of its own
// filters, which are defined in code.
const props = defineProps({
	doctype: { type: String, default: null },
	fields: { type: Array, default: null },
	record: { type: Object, required: true },
	locked: { type: Boolean, default: false },
	on_change: { type: Function, required: true },
});

const saved = JSON.parse(props.record.filters_json || "{}");
const values = reactive(Array.isArray(saved) ? {} : saved);

// a filter's options and conditions may be code, which a layout cannot carry
const select_options = (options) =>
	(Array.isArray(options) ? options : []).map((option) => option?.value ?? option).join("\n");

const layout = computed(() =>
	buildLayoutFromMeta(
		(props.fields || []).map((df) => ({
			fieldname: df.fieldname,
			fieldtype: df.fieldtype,
			label: df.label && window.__(df.label),
			options: typeof df.options === "string" ? df.options : select_options(df.options),
			reqd: df.reqd,
			read_only: props.locked,
		}))
	)
);

onMounted(() => {
	if (!props.fields || props.locked || Object.keys(values).length) return;
	Object.assign(values, window.frappe.report_utils.get_filter_values(props.fields));
});

watch(values, () => props.on_change(JSON.stringify(values)));
</script>

<template>
	<FieldRows v-if="fields" :layout="layout" :doc="values" />
	<fieldset v-else class="contents" :disabled="locked">
		<InlineFilter
			:key="doctype"
			:doctype="doctype"
			:filters="filter_rows(record.filters_json, doctype)"
			@change="(rows) => on_change(JSON.stringify(rows))"
		/>
	</fieldset>
</template>
