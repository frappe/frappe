<template>
	<div class="pfb-insp-body">
		<InspectorSection
			v-for="sec in sections"
			:key="sec.key"
			:label="sec.label()"
			:init-open="sec.init_open !== false"
			:padded="false"
		>
			<div v-if="sec.rows.length" class="pfb-insp-section-body">
				<component
					v-for="row in sec.rows"
					:key="row.key"
					:is="row.component"
					v-bind="row_props(row)"
					v-on="row_listeners(row)"
				/>
			</div>
			<component
				v-for="row in sec.after"
				:key="row.key"
				:is="row.component"
				v-bind="row_props(row)"
				v-on="row_listeners(row)"
			/>
		</InspectorSection>
		<div v-if="is_multi" class="pfb-insp-section-body">
			<button
				class="es-button pfb-bulk-remove"
				data-variant="subtle"
				data-theme="red"
				@click="store.remove_selection()"
			>
				{{ __("Remove selected") }}
			</button>
		</div>
	</div>
</template>

<script setup>
import { computed } from "vue";
import InspectorSection from "./InspectorSection.vue";
import { FIELD_SECTIONS } from "./field_properties";
import { useSelectedField } from "./useSelectedField";
import { section_of } from "../../layout";
import { set_prop } from "../../utils";

const { store, selected_field, selected_fields } = useSelectedField();

const is_multi = computed(() => store.is_multi_select.value);
const fields = computed(() =>
	is_multi.value ? selected_fields.value : selected_field.value ? [selected_field.value] : []
);
const ctx = {
	set: set_prop,
	get print_format() {
		return store.print_format.value;
	},
	inline: (df) => section_of(store.layout.value, df)?.field_orientation === "left-right",
};

function visible(rows) {
	if (!fields.value.length) return [];
	return rows.filter(
		(row) =>
			(is_multi.value ? !row.single : !row.multi) &&
			fields.value.every((df) => !row.when || row.when(df, ctx))
	);
}
const sections = computed(() =>
	FIELD_SECTIONS.map((sec) => ({
		...sec,
		rows: visible(sec.rows),
		after: visible(sec.after || []),
	})).filter((sec) => sec.rows.length || sec.after.length)
);

const MIXED = Symbol("mixed");
function value(row) {
	const values = fields.value.map((df) => (row.get ? row.get(df, ctx) : df[row.key]));
	return values.every((v) => v === values[0]) ? values[0] : MIXED;
}
function row_props(row) {
	const props = row.props ? row.props(fields.value[0], ctx) : {};
	if (row.bare) return props;
	const v = value(row);
	if (v !== MIXED) return { ...props, modelValue: v };
	const mixed = { ...props, modelValue: row.mixed ?? "" };
	if (row.component.props?.placeholder) mixed.placeholder = __("Mixed");
	return mixed;
}
function each(fn) {
	return (v) => fields.value.forEach((df) => fn(df, v, ctx));
}
function row_listeners(row) {
	if (row.bare) return {};
	const listeners = {
		"update:modelValue": each(row.set || ((df, v) => set_prop(df, row.key, v))),
	};
	for (const [event, fn] of Object.entries(row.on || {})) listeners[event] = each(fn);
	return listeners;
}
</script>

<style scoped>
.pfb-bulk-remove {
	align-self: flex-start;
}
</style>
