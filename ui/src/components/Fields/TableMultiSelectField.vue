<template>
	<TableMultiSelect
		ref="control"
		v-model="value"
		v-model:open="open"
		:doctype="targetDoctype"
		:filters="field.filters"
		:label="field.label"
		:description="
			targetDoctype
				? field.description
				: 'Child table metadata unavailable — picker disabled.'
		"
		:placeholder="field.placeholder"
		:required="field.reqd"
		:disabled="field.readOnly || !targetDoctype"
		:titles="titles"
		:creatable="linkCreate.creatable.value"
		@create="linkCreate.create"
	>
		<template #create="{ query }">{{ linkCreate.label(query) }}</template>
	</TableMultiSelect>
</template>

<script setup lang="ts">
// Frappe `Table MultiSelect`: child rows whose Link field names the target doctype, bridged to
// the control's `string[]` by `useChildRowModel`. Creates through `useLinkCreate`, like `LinkField`.
import { computed, ref } from "vue";
import { TableMultiSelect } from "../TableMultiSelect";
import type { TableMultiSelectExposed } from "../TableMultiSelect";
import { useChildRowModel } from "../FormLayout/useChildRowModel";
import { newRowValues } from "../FormLayout/newRowValues";
import type { FieldComponentEmits, FieldComponentProps } from "./types";
import { useLinkCreate } from "./useLinkCreate";

const props = defineProps<FieldComponentProps>();
const emit = defineEmits<FieldComponentEmits>();

// Link field's `options` is the target doctype; its `fieldname` is the key each row stores the value under.
const linkField = computed(() => props.field.childFields?.find((f) => f.fieldtype === "Link"));
const targetDoctype = computed(() => linkField.value?.options ?? "");

const value = useChildRowModel(
	() => props.modelValue,
	() => linkField.value?.fieldname ?? "",
	emit,
	() => props.field.fieldname,
	// A picked row is a new child row, so it starts out shaped like any other.
	// `childFields` is the child's grid-column subset, not its whole form — a
	// `Table MultiSelect` node carries no `childLayout` — so the seed narrows to
	// those. Known limit, not a hole: it is the same subset the picker itself shows.
	() => newRowValues(props.field.childFields ?? [])
);

const control = ref<TableMultiSelectExposed | null>(null);
const open = ref(false);

const linkCreate = useLinkCreate({
	doctype: targetDoctype,
	filters: () => props.field.filters,
	disabled: () => Boolean(props.field.readOnly),
	open,
	link: control,
	select: (name) => {
		if (!value.value.includes(name)) value.value = [...value.value, name];
	},
});

const titles = computed(() => {
	const titled = value.value.flatMap((name) => {
		const title = linkCreate.title(name);
		return title ? [[name, title] as const] : [];
	});
	return Object.fromEntries(titled);
});
</script>
