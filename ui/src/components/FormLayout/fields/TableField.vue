<template>
	<Grid
		v-model="rows"
		:columns="columns"
		:disabled="field.readOnly"
		:label="field.label"
		:required="field.reqd"
		@change="(r: Record<string, any>[]) => emit('change', r)"
	>
		<template #cell="{ column, value, update, commit }">
			<component
				:is="resolveField(cellField(column.fieldname).fieldtype)"
				class="w-full"
				:field="cellField(column.fieldname)"
				:modelValue="value"
				@update:modelValue="update"
				@change="commit"
			/>
		</template>
	</Grid>
</template>

<script setup lang="ts">
import { computed, inject } from "vue";
import { Grid } from "../../Grid";
import { ResolveFieldKey } from "../types";
import type { FieldComponentEmits, FieldComponentProps, FieldMeta } from "../types";

const props = defineProps<FieldComponentProps>();
const emit = defineEmits<FieldComponentEmits>();

// Reuse the form's fieldtype registry so each cell is rendered by the registered
// (app-overridable) field component. This is FormLayout's concern, not the
// generic Grid's — hence it lives here, in the `#cell` slot.
const resolveField = inject(ResolveFieldKey)!;

const columns = computed<FieldMeta[]>(() => props.field.childFields ?? []);

// Label-less copies keyed by fieldname: the grid header already shows each
// column's label, so cells render without one (otherwise every control repeats
// the column heading inside the row). Keyed lookup because the generic Grid
// hands the slot back a minimal column shape, not the full FieldMeta.
const cellFields = computed<Record<string, FieldMeta>>(() =>
	Object.fromEntries(
		columns.value.map((c) => [c.fieldname, { ...c, label: undefined, description: undefined }])
	)
);

function cellField(fieldname: string): FieldMeta {
	return cellFields.value[fieldname];
}

const rows = computed<Record<string, any>[]>({
	get: () => (Array.isArray(props.modelValue) ? props.modelValue : []),
	set: (v) => emit("update:modelValue", v),
});
</script>
