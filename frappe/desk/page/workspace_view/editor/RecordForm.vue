<script setup>
import { computed, onMounted, ref, shallowRef, watch } from "vue";
import { buildLayoutFromMeta } from "@framework/ui/FormLayout";
import FieldRows from "./FieldRows.vue";
import RecordFilters from "./RecordFilters.vue";
import { attempt } from "../api.js";
import { RECORDS, load_source } from "./records.js";

// A record's own form, drawn from its doctype's meta, editing the widget's copy of it.
const props = defineProps({
	type: { type: String, required: true },
	widget: { type: Object, required: true },
	locked: { type: Boolean, default: false },
});

const emit = defineEmits(["change"]);
const __ = window.__;
const spec = RECORDS[props.type];
const record = computed(() => props.widget.record);
const meta = shallowRef(null);
const source = ref({});

onMounted(() =>
	attempt(async () => {
		await window.frappe.model.with_doctype(spec.doctype);
		meta.value = window.frappe.get_meta(spec.doctype);
	})
);

function translated(df) {
	return {
		...df,
		label: df.label && __(df.label),
		description: df.description && __(df.description),
	};
}

function locked_field(df) {
	return { ...df, read_only: 1, read_only_depends_on: undefined };
}

function field_of(df) {
	const hidden = spec.hidden?.(record.value, source.value) || [];
	const field = {
		...translated(df),
		hidden: df.hidden || hidden.includes(df.fieldname),
		read_only: df.read_only || (df.set_only_once && record.value.name),
		filters: spec.link_filters?.[df.fieldname]?.(source.value),
	};
	return props.locked ? locked_field(field) : field;
}

function child_metas() {
	const tables = meta.value.fields.filter((df) => df.fieldtype.startsWith("Table"));
	return Object.fromEntries(
		tables.map(({ options }) => [
			options,
			window.frappe
				.get_meta(options)
				.fields.map(translated)
				.map((df) => (props.locked ? locked_field(df) : df)),
		])
	);
}

function decorate({ fieldname }) {
	const options = spec.options?.[fieldname]?.(record.value, source.value);
	const after = spec.after?.[fieldname];
	return {
		...(options && { props: { options } }),
		...(after && { on: { change: () => after(record.value) } }),
	};
}

function filters_part() {
	const { filters } = source.value;
	const doctype = filters ? null : record.value.document_type;
	if (!filters?.length && !doctype) return null;
	return {
		name: "filters",
		component: RecordFilters,
		props: {
			doctype,
			fields: filters,
			record: record.value,
			locked: props.locked,
			on_change: (value) => (record.value.filters_json = value),
		},
	};
}

// The pane holds one column, and a filters section draws a filter editor over its raw JSON.
const layout = computed(() => {
	if (!meta.value) return [];
	const tabs = buildLayoutFromMeta(meta.value.fields.map(field_of), {
		childMetas: child_metas(),
		decorate,
	});
	for (const section of tabs.flatMap((tab) => tab.sections)) {
		section.columns = [{ fields: section.columns.flatMap((column) => column.fields) }];
		if (section.name !== "filters_section") continue;
		section.label = __("Filters");
		section.part = filters_part();
		section.hidden = !section.part;
	}
	return tabs;
});

const source_key = computed(() =>
	JSON.stringify((spec.source_fields || []).map((field) => record.value[field]))
);

watch(
	source_key,
	() =>
		spec.source_fields &&
		attempt(async () => {
			const key = source_key.value;
			const loaded = await load_source(props.type, record.value);
			if (key !== source_key.value) return;
			source.value = loaded;
			if (!props.locked && loaded.parents?.length === 1) {
				record.value.parent_document_type ||= loaded.parents[0];
			}
		}),
	{ immediate: true }
);

// Saving replaces the copy, and only an edit changes the one that is there.
watch(
	record,
	(now, before) => {
		if (now !== before) return;
		props.widget.record_changed = true;
		spec.preview?.(props.widget);
		emit("change");
	},
	{ deep: true }
);
</script>

<template>
	<FieldRows v-if="layout.length" :layout="layout" :doc="record" />
</template>
