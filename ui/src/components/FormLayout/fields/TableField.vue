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
			<!-- Resolve the column's conditional read-only/mandatory/hidden against
			     THIS row, so a per-row condition shows in the grid cell exactly as it
			     does in the row-edit dialog (which evaluates the same expressions
			     against the same row). A row whose `depends_on` is false renders an
			     empty, non-editable cell — desk's per-row grid behaviour. -->
			<template v-if="!cellField(column.fieldname, row).hidden">
				<!-- Compact controls (checkbox/rating) center at their natural size;
				     everything else fills the cell. `row` is passed so a cell can
				     resolve `options`-points-to-a-sibling-field conventions (e.g. a
				     Currency code) against its own row, not the parent doc. -->
				<div
					v-if="isCentered(column.fieldname)"
					class="flex w-full items-center justify-center"
				>
					<component
						:is="resolveField(cellField(column.fieldname, row).fieldtype)"
						:field="cellField(column.fieldname, row)"
						:modelValue="value"
						:row="row"
						@update:modelValue="update"
						@change="commit"
					/>
				</div>
				<component
					:is="resolveField(cellField(column.fieldname, row).fieldtype)"
					v-else
					class="w-full"
					:field="cellField(column.fieldname, row)"
					:modelValue="value"
					:row="row"
					@update:modelValue="update"
					@change="commit"
				/>
			</template>
			<template v-else>
				<!-- Hidden per-row: render an EMPTY placeholder, not nothing. A slot
				     that renders only comments (a bare `v-if` with no else) makes Vue
				     fall back to the Grid's default `#cell` content — which prints the
				     raw value (`{{ row[fieldname] }}`). A real (empty) vnode suppresses
				     that. -->
				<span class="w-full" />
			</template>
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
import { computed, defineAsyncComponent, inject, provide, ref } from "vue";
import { Dialog } from "frappe-ui";
import { Grid } from "../../Grid";
import type { GridColumn } from "../../Grid";
import { fieldsToLayout } from "../fieldsToLayout";
import { resolveFieldConditionals } from "../resolveLayout";
import { DocKey, ParentDocKey, ResolveFieldKey } from "../types";
import type {
	FieldComponentEmits,
	FieldComponentProps,
	FieldMeta,
	FormLayoutSchema,
} from "../types";

// Async to break the module cycle (fieldTypes → TableField → FormLayout →
// fieldTypes); the row form is only needed once the dialog opens anyway.
const FormLayout = defineAsyncComponent(() => import("../FormLayout.vue"));

const props = defineProps<FieldComponentProps>();
const emit = defineEmits<FieldComponentEmits>();

// Reuse the form's fieldtype registry so each cell is rendered by the registered
// (app-overridable) field component. This is FormLayout's concern, not the
// generic Grid's — hence it lives here, in the `#cell` slot.
const resolveField = inject(ResolveFieldKey)!;

// Expose this table's own doc as the *parent* doc for its rows. A row's fields
// (grid cells and the row-edit dialog alike) then resolve parent-scoped options
// against it — e.g. a Currency `options` that names a parent field. Without
// this, the dialog's nested FormLayout shadows `DocKey` with the row clone and
// the row would lose sight of the parent, desyncing currency formatting from the
// grid. Null at the top level (no parent doc to inject).
const parentDoc = inject(DocKey, null);
provide(ParentDocKey, parentDoc);

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

// The cell's field meta, with its conditional read-only/mandatory/hidden
// expressions resolved against `row` (`doc`) and the table's own doc (`parent`,
// so a `eval:parent.x` reaches the parent — desk's `parent = this.frm.doc`).
// This mirrors the row-edit dialog, which resolves the same expressions against
// the same row + parent, so a per-row condition reads identically in both. The
// call is reactive: `evaluateDependsOn` reads the row's (and parent's) values,
// so the cell re-resolves when an in-place edit changes a field it depends on.
//
// A read-only table forces every cell read-only too (desk: a read-only grid is a
// viewer). Per-field/conditional read-only still applies on top via
// `resolveFieldConditionals`; the table flag only ever adds read-only, never lifts it.
function cellField(fieldname: string, row: Record<string, any>): FieldMeta {
	const f = resolveFieldConditionals(cellFields.value[fieldname], row, parentDoc?.value ?? row);
	return props.field.readOnly ? { ...f, readOnly: true } : f;
}

// Compact controls render at their natural size, centered in the cell (a
// full-width checkbox/rating looks broken — see the stretched checkbox bug).
// Everything else fills the cell width. Fieldtype is static, so this reads the
// base column meta — no per-row resolution needed.
function isCentered(fieldname: string): boolean {
	return CENTERED_FIELDTYPES.has(cellFields.value[fieldname].fieldtype);
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

// The dialog renders the child doctype's *full* form — every field, in the
// child's own tabs/sections (desk's grid-row behaviour) — not just the grid
// columns. `childLayout` carries that full layout (built from the child meta);
// fall back to a flat form of the visible columns when it's absent (e.g. the
// static-schema flow that supplies `childFields` but no `childLayout`).
//
// A read-only table opens the dialog as a *viewer*: every field is forced
// read-only so the row can be inspected but not edited (it would otherwise let a
// user edit and commit back into a table the grid won't let them touch).
const editLayout = computed(() => {
	const base = props.field.childLayout ?? fieldsToLayout(columns.value);
	return props.field.readOnly ? readOnlyLayout(base) : base;
});

// Force every field in a layout read-only, returning a fresh tree (never mutates
// the shared child layout). Mirrors `resolveLayout`'s walk; used only for the
// read-only table's row dialog.
function readOnlyLayout(schema: FormLayoutSchema): FormLayoutSchema {
	return schema.map((tab) => ({
		...tab,
		sections: tab.sections.map((section) => ({
			...section,
			columns: section.columns.map((column) => ({
				...column,
				fields: column.fields.map((f) => ({ ...f, readOnly: true })),
			})),
		})),
	}));
}

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
