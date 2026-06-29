<template>
	<Grid
		v-model="rows"
		:columns="columns"
		:disabled="field.readOnly"
		:label="field.label"
		:description="field.description"
		:required="field.reqd"
		@change="(r: Record<string, any>[]) => emit('change', r)"
		@edit="openEdit"
	>
		<template #cell="{ row, column, value, update, commit }">
			<!-- Resolve conditionals against THIS row (so per-row conditions match the
			     row-edit dialog, and `row` lets a cell resolve `options`-to-sibling-field
			     like a Currency code against its own row). The single-item `v-for` binds
			     the resolved field to `f` once per cell: `cellField` re-runs
			     `resolveFieldConditionals` (potentially an `eval:` `new Function`), so
			     binding once avoids repeating that work for every `f.` reference below. -->
			<template v-for="f in [cellField(column.fieldname, row)]" :key="column.fieldname">
				<template v-if="!f.hidden">
					<!-- Fieldtypes whose editor can't fit a single-row cell (multi-line
					     code editors, nested grids, display-only blocks) render a compact
					     read-only summary here; the row-edit dialog renders the real
					     control. Button stays inline — it carries no value and its label
					     fits a cell. -->
					<span
						v-if="isSummaryField(f)"
						class="truncate px-2 py-1 text-sm text-ink-gray-5"
						:title="cellSummary(f, value, row)"
					>
						{{ cellSummary(f, value, row) }}
					</span>
					<div
						v-else-if="isCentered(column.fieldname)"
						class="flex w-full items-center justify-center"
					>
						<component
							:is="f.ui?.component ?? resolveField(f.fieldtype)"
							:field="f"
							:modelValue="value"
							:row="row"
							@update:modelValue="update"
							@change="commit"
							v-bind="f.ui?.props"
							v-on="cellListeners(f, row)"
						/>
					</div>
					<component
						:is="f.ui?.component ?? resolveField(f.fieldtype)"
						v-else
						class="w-full"
						:field="f"
						:modelValue="value"
						:row="row"
						@update:modelValue="update"
						@change="commit"
						v-bind="f.ui?.props"
						v-on="cellListeners(f, row)"
					/>
				</template>
				<template v-else>
					<!-- Empty vnode, not nothing: a comments-only slot makes Vue fall back to
					     Grid's default `#cell`, which prints the raw value. -->
					<span class="w-full" />
				</template>
			</template>
		</template>
	</Grid>

	<!-- Row-edit: render the full row as a FormLayout form (Grid only emits `edit`). -->
	<Dialog v-model:open="showEdit" :title="dialogTitle" size="3xl">
		<FormLayout v-if="editIndex !== null" v-model:doc="editDoc" :layout="editLayout" />
	</Dialog>
</template>

<script setup lang="ts">
import { computed, defineAsyncComponent, inject, provide, ref, watch } from "vue";
import { Dialog } from "frappe-ui";
import { Grid } from "../Grid";
import type { GridColumn } from "../Grid";
import { fieldsToLayout } from "../FormLayout/fieldsToLayout";
import { resolveFieldConditionals } from "../FormLayout/resolveLayout";
import { DocKey, ParentDocKey } from "./types";
import { ResolveFieldKey } from "../FormLayout/types";
import type { FieldComponentEmits, FieldComponentProps } from "./types";
import type { FieldNode, FormLayoutSchema } from "../FormLayout/types";

// Async to break the module cycle (fieldTypes → TableField → FormLayout → fieldTypes).
const FormLayout = defineAsyncComponent(() => import("../FormLayout/FormLayout.vue"));

const props = defineProps<FieldComponentProps>();
const emit = defineEmits<FieldComponentEmits>();

// Reuse the form's fieldtype registry so each cell uses the registered (app-overridable) component.
const resolveField = inject(ResolveFieldKey)!;

// Expose this table's doc as the *parent* for its rows so rows resolve parent-scoped
// options. Without it, the dialog's nested FormLayout shadows `DocKey`, desyncing
// currency formatting from the grid. Null at the top level.
const parentDoc = inject(DocKey, null);
provide(ParentDocKey, parentDoc);

// Per-fieldtype alignment, applied to header + cells so they agree. Numeric
// right-aligns (desk); checkbox/rating center.
const NUMBER_FIELDTYPES = new Set(["Int", "Float", "Currency", "Percent"]);
const CENTERED_FIELDTYPES = new Set(["Check", "Rating"]);

// Fieldtypes whose editor can't live in a 34px single-row cell — multi-line code
// editors, nested grids, and display-only blocks. The cell renders a read-only
// summary instead; the row-edit dialog renders the full control. Button is NOT
// here: it carries no value and its label fits a cell.
const SUMMARY_FIELDTYPES = new Set([
	"Code",
	"JSON",
	"Markdown Editor",
	"HTML Editor",
	"Table",
	"Table MultiSelect",
	"Image",
	"Heading",
	"HTML",
]);

// Cells normally drop their label (the header carries it), but a couple of
// fieldtypes render the label as content: Button labels its action, and a
// Heading's summary echoes it.
const KEEP_CELL_LABEL = new Set(["Button", "Heading"]);

function alignFor(fieldtype: string): GridColumn["align"] {
	if (NUMBER_FIELDTYPES.has(fieldtype)) return "right";
	if (CENTERED_FIELDTYPES.has(fieldtype)) return "center";
	return undefined;
}

const columns = computed<(FieldNode & Pick<GridColumn, "align">)[]>(() =>
	(props.field.childFields ?? []).map((c) => ({ ...c, align: alignFor(c.fieldtype) }))
);

// Label-less copies keyed by fieldname: the header already shows the label, so cells
// drop it (else every control repeats the heading) — except the few fieldtypes whose
// label IS their content (`KEEP_CELL_LABEL`). Keyed because the Grid slot hands back a
// minimal column shape, not the full FieldMeta.
const cellFields = computed<Record<string, FieldNode>>(() =>
	Object.fromEntries(
		columns.value.map((c) => [
			c.fieldname,
			{
				...c,
				label: KEEP_CELL_LABEL.has(c.fieldtype) ? c.label : undefined,
				description: undefined,
			},
		])
	)
);

// Resolve the cell's conditionals against `row` (doc) and the table's doc (parent, so
// `eval:parent.x` reaches it). Reactive, so the cell re-resolves on in-place edits.
// A read-only table forces every cell read-only (only ever adds, never lifts it).
function cellField(fieldname: string, row: Record<string, any>): FieldNode {
	const f = resolveFieldConditionals(cellFields.value[fieldname], row, parentDoc?.value ?? row);
	return props.field.readOnly ? { ...f, readOnly: true } : f;
}

// Bind the node's `ui.on` handlers onto the cell, injecting the row as a trailing
// arg (`on.click(event, row)` / `on.change(value, row)`) — top-level fields get no
// row, so the convention is back-compatible. Composed handler arrays all fire.
// Returned alongside the grid's own `@change`/`@update:modelValue`; Vue merges
// same-event listeners so both the row-write and any `ui.on.change` run.
function cellListeners(
	field: FieldNode,
	row: Record<string, any>
): Record<string, (...args: any[]) => void> {
	const on = field.ui?.on;
	if (!on) return {};
	const bound: Record<string, (...args: any[]) => void> = {};
	for (const [event, handler] of Object.entries(on)) {
		const handlers = Array.isArray(handler) ? handler : [handler];
		bound[event] = (...args: any[]) => handlers.forEach((h) => h(...args, row));
	}
	return bound;
}

// Center compact controls at natural size (a full-width checkbox/rating looks broken).
function isCentered(fieldname: string): boolean {
	return CENTERED_FIELDTYPES.has(cellFields.value[fieldname].fieldtype);
}

function isSummaryField(field: FieldNode): boolean {
	return SUMMARY_FIELDTYPES.has(field.fieldtype);
}

// Compact read-only text for a summary cell: a count for collections, resolved
// presence for an Image, the label for a Heading, stripped text for HTML, and a
// one-line collapse of the raw string for the code editors. Editing happens in
// the row-edit dialog, which renders the real control.
function cellSummary(field: FieldNode, value: any, row: Record<string, any>): string {
	switch (field.fieldtype) {
		case "Table": {
			const n = Array.isArray(value) ? value.length : 0;
			return n ? `${n} row${n === 1 ? "" : "s"}` : "—";
		}
		case "Table MultiSelect": {
			const n = Array.isArray(value) ? value.length : 0;
			return n ? `${n} selected` : "—";
		}
		case "Image": {
			// Image mirrors the sibling field named in `options` (else its own value).
			const url = field.options ? row?.[field.options] : value;
			return url ? "Image" : "—";
		}
		case "Heading":
			return field.label ?? "";
		case "HTML": {
			const text = (field.options ?? "")
				.replace(/<[^>]*>/g, " ")
				.replace(/\s+/g, " ")
				.trim();
			return text || "HTML";
		}
		default: {
			// Code / JSON / Markdown Editor / HTML Editor — collapse to a single line.
			const s = value == null ? "" : String(value).replace(/\s+/g, " ").trim();
			return s || "—";
		}
	}
}

const rows = computed<Record<string, any>[]>({
	get: () => (Array.isArray(props.modelValue) ? props.modelValue : []),
	set: (v) => emit("update:modelValue", v),
});

// --- Row-edit dialog ---------------------------------------------------------

// `editIndex` null = dialog closed. `editDoc` is a clone so the dialog edits in
// isolation; commits copy it back into the rows array.
const editIndex = ref<number | null>(null);
const editDoc = ref<Record<string, any>>({});
// The row object being edited, tracked by identity so write-back survives a
// parent re-sort/filter of the rows array between watcher fires (a cached
// positional index would point at the wrong row after reorder).
const editRow = ref<Record<string, any> | null>(null);

const showEdit = computed({
	get: () => editIndex.value !== null,
	set: (open) => {
		if (!open) editIndex.value = null;
	},
});

const dialogTitle = computed(() =>
	editIndex.value === null ? "" : `${props.field.label ?? "Row"} — Row ${editIndex.value + 1}`
);

// Dialog renders the child's full form via `childLayout`; fall back to a flat form of
// the visible columns when absent. A read-only table forces every field read-only.
const editLayout = computed(() => {
	const base = props.field.childLayout ?? fieldsToLayout(columns.value);
	return props.field.readOnly ? readOnlyLayout(base) : base;
});

// Force every field read-only, returning a fresh tree (never mutates the shared layout).
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
	// Seeding the clone reassigns `editDoc`, which would trip the write-back watch
	// (a no-op echo of the unedited row that needlessly churns the row's identity
	// and emits a phantom change). Suppress that one open-time fire.
	skipWriteBack = true;
	editRow.value = rows.value[index];
	editDoc.value = { ...editRow.value };
	editIndex.value = index;
}

// Write the working copy back into the row. `FormLayout` emits nothing now, so we
// watch the dialog's reactive doc (deep) instead of an `@change` event; the doc
// syncs live, so this writes back as the user edits (vs. the old commit-only
// `@change`), flowing through the same `update:modelValue`/`change` the grid expects.
let skipWriteBack = false;
watch(
	editDoc,
	() => {
		if (editIndex.value === null) return;
		if (skipWriteBack) {
			skipWriteBack = false;
			return;
		}
		const next = rows.value.slice();
		// Locate the row by identity, not the cached index: the parent may have
		// re-sorted/filtered `rows` since open, so the positional index can now
		// point at a different row.
		const i = editRow.value ? next.indexOf(editRow.value) : -1;
		if (i === -1) return; // row was removed/reordered out externally
		// Mutate the row in place (vs. replacing it) so its object reference is
		// preserved — the Grid keys rows by identity via a WeakMap, so a fresh
		// object would re-key and re-mount the row, dropping its selection state.
		Object.assign(next[i], editDoc.value);
		emit("update:modelValue", next);
		emit("change", next);
	},
	{ deep: true }
);
</script>
