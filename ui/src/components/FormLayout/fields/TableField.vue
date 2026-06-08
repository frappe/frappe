<template>
	<Grid
		v-model="rows"
		:columns="columns"
		:disabled="field.readOnly"
		:label="field.label"
		:required="field.reqd"
		@change="(r: Record<string, any>[]) => emit('change', r)"
		@edit="openEdit"
	>
		<template #cell="{ row, column, value, update, commit }">
			<!-- Compact controls (checkbox/rating) center at their natural size;
			     everything else fills the cell. `row` is passed so a cell can
			     resolve `options`-points-to-a-sibling-field conventions (e.g. a
			     Currency code) against its own row, not the parent doc. -->
			<div
				v-if="isCentered(column.fieldname)"
				class="flex w-full items-center justify-center"
			>
				<component
					:is="resolveField(cellField(column.fieldname).fieldtype)"
					:field="cellField(column.fieldname)"
					:modelValue="value"
					:row="row"
					@update:modelValue="update"
					@change="commit"
				/>
			</div>
			<component
				:is="resolveField(cellField(column.fieldname).fieldtype)"
				v-else
				class="w-full"
				:field="cellField(column.fieldname)"
				:modelValue="value"
				:row="row"
				@update:modelValue="update"
				@change="commit"
			/>
		</template>
	</Grid>

	<!-- Row-edit action: render the full row as a form with FormLayout. This is
	     FormLayout's concern (it owns the schema + field registry), so it lives
	     here, not in the generic Grid — the grid only emits `edit`. -->
	<Dialog v-model="showEdit" :options="{ title: dialogTitle, size: '3xl' }">
		<template #body-content>
			<FormLayout
				v-if="editIndex !== null"
				v-model:doc="editDoc"
				:layout="editLayout"
				@change="commitEdit"
			/>
		</template>
	</Dialog>
</template>

<script setup lang="ts">
import { computed, defineAsyncComponent, inject, ref } from "vue";
import { Dialog } from "frappe-ui";
import { Grid } from "../../Grid";
import type { GridColumn } from "../../Grid";
import { fieldsToLayout } from "../fieldsToLayout";
import { ResolveFieldKey } from "../types";
import type { FieldComponentEmits, FieldComponentProps, FieldMeta } from "../types";

// Async to break the module cycle (fieldTypes → TableField → FormLayout →
// fieldTypes); the row form is only needed once the dialog opens anyway.
const FormLayout = defineAsyncComponent(() => import("../FormLayout.vue"));

const props = defineProps<FieldComponentProps>();
const emit = defineEmits<FieldComponentEmits>();

// Reuse the form's fieldtype registry so each cell is rendered by the registered
// (app-overridable) field component. This is FormLayout's concern, not the
// generic Grid's — hence it lives here, in the `#cell` slot.
const resolveField = inject(ResolveFieldKey)!;

// Per-fieldtype column alignment, applied to the header label *and* the cells so
// they always agree (the Grid honours `align` on each column). Numeric columns
// right-align like Frappe desk; compact centered controls (checkbox/rating) get a
// centered header to sit over their centered cell.
const NUMBER_FIELDTYPES = new Set(["Int", "Float", "Currency", "Percent"]);
const CENTERED_FIELDTYPES = new Set(["Check", "Rating"]);

function alignFor(fieldtype: string): GridColumn["align"] {
	if (NUMBER_FIELDTYPES.has(fieldtype)) return "right";
	if (CENTERED_FIELDTYPES.has(fieldtype)) return "center";
	return undefined;
}

const columns = computed<(FieldMeta & Pick<GridColumn, "align">)[]>(() =>
	(props.field.childFields ?? []).map((c) => ({ ...c, align: alignFor(c.fieldtype) }))
);

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

// Compact controls render at their natural size, centered in the cell (a
// full-width checkbox/rating looks broken — see the stretched checkbox bug).
// Everything else fills the cell width.
function isCentered(fieldname: string): boolean {
	return CENTERED_FIELDTYPES.has(cellField(fieldname).fieldtype);
}

const rows = computed<Record<string, any>[]>({
	get: () => (Array.isArray(props.modelValue) ? props.modelValue : []),
	set: (v) => emit("update:modelValue", v),
});

// --- Row-edit dialog ---------------------------------------------------------

// The row being edited (null = dialog closed). `editDoc` is a clone so the
// dialog edits in isolation; field commits copy it back into the rows array.
const editIndex = ref<number | null>(null);
const editDoc = ref<Record<string, any>>({});

const showEdit = computed({
	get: () => editIndex.value !== null,
	set: (open) => {
		if (!open) editIndex.value = null;
	},
});

const dialogTitle = computed(() =>
	editIndex.value === null ? "" : `${props.field.label ?? "Row"} — Row ${editIndex.value + 1}`
);

// The dialog renders the *labelled* child fields (a real form), unlike the
// label-less cell copies used inside the grid.
const editLayout = computed(() => fieldsToLayout(columns.value));

function openEdit({ index }: { row: Record<string, any>; index: number }) {
	editDoc.value = { ...rows.value[index] };
	editIndex.value = index;
}

// FormLayout commits a field (blur/selection) → write the working copy back into
// the row, emitting both the value sync and the intentful change.
function commitEdit() {
	if (editIndex.value === null) return;
	const next = rows.value.slice();
	next[editIndex.value] = { ...editDoc.value };
	emit("update:modelValue", next);
	emit("change", next);
}
</script>
