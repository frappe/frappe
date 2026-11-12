<!--
  The List type's renderer: the table with its bulk bar and footer, and the column settings among
  the page's controls. The composable holds the state; this lays it out.
-->
<template>
	<Teleport v-if="host.controls.value" :to="host.controls.value">
		<ColumnSettings
			v-model="columns"
			:doctype="view.doctype"
			:canReset="columnsCustomized"
			@reset="resetColumns"
		/>
	</Teleport>
	<PageState v-if="error" v-bind="failedState(error, reload)" />
	<List
		v-else
		ref="table"
		v-model:selection="selection"
		v-model:cursor="cursor"
		v-model:sort="sort"
		:columns="shownColumns"
		:rows="rows"
		:loading="loading"
		:rowLink="rowLink"
		:rowMenu="rowActions.length > 0"
		:cellClass="(row, column) => seenClassOf(row, column.fieldname)"
		gutter="var(--page-gutter)"
		@column-resize="resizeColumn($event.fieldname, $event.width)"
		@column-reset="resetColumnWidth($event.fieldname)"
		@row-contextmenu="menu.open($event.name, $event.event)"
		@pointerover="bulk.prefetch"
		@focusin="bulk.prefetch"
	>
		<template v-if="selection.length && bulk.parts.value" #bar>
			<component
				:is="bulk.parts.value.chunk.BulkBar"
				:scope="scope"
				:doctype="view.doctype"
				:status="bulk.parts.value.status"
				:cap="bulk.cap"
				:layout="bulk.layout.value"
				:locked="bulk.locked"
				v-model:menuOpen="bulk.menuOpen.value"
				@clear="scope.clear()"
			/>
		</template>
		<template #cell="{ row, column, value }">
			<FavouriteCell
				v-if="column.fieldname === '_favourite'"
				:doctype="view.doctype"
				:name="row.name"
			/>
			<AvatarStackCell
				v-else-if="column.fieldname === '_assign' || column.fieldname === '_liked_by'"
				:value="value"
			/>
			<TagsCell v-else-if="column.fieldname === '_user_tags'" :value="value" />
			<DocstatusCell v-else-if="column.fieldname === 'docstatus'" :value="value" />
			<CommentsCell
				v-else-if="column.fieldname === '_comments'"
				:doctype="view.doctype"
				:name="row.name"
			/>
			<EmailCell
				v-else-if="emailFields.has(column.fieldname)"
				:field="emailFields.get(column.fieldname)!"
				:value="value"
				:doctype="view.doctype"
				:name="row.name"
			/>
			<PhoneCell
				v-else-if="phoneFields.has(column.fieldname)"
				:field="phoneFields.get(column.fieldname)!"
				:value="value"
			/>
			<ConfiguredCell
				v-else-if="
					cellViewOf(column.fieldname, value, row) && cellFields.has(column.fieldname)
				"
				:field="cellFields.get(column.fieldname)!"
				:row="row"
				:view="cellViewOf(column.fieldname, value, row)!"
				@filter="applyBadgeFilters"
			/>
			<div v-else-if="markOf(column.fieldname)" class="flex min-w-0 items-center">
				<LinkMark
					class="me-1.5"
					:source="markOf(column.fieldname)!.source"
					:value="row[markOf(column.fieldname)!.key]"
					:text="markedText(row, column.fieldname)"
				/>
				<div class="truncate text-base text-ink-gray-8">
					{{ markedText(row, column.fieldname) }}
				</div>
			</div>
			<SwitchCell
				v-else-if="switchOf(column.fieldname) && cellFields.has(column.fieldname)"
				:doctype="view.doctype"
				:field="cellFields.get(column.fieldname)!"
				:row="row"
				:writable="canWrite(column.fieldname)"
			/>
			<StatusCell
				v-else-if="
					statusThemeOf(column.fieldname, value) && cellFields.has(column.fieldname)
				"
				:field="cellFields.get(column.fieldname)!"
				:row="row"
				:theme="statusThemeOf(column.fieldname, value)!"
			/>
			<FieldCell
				v-else-if="cellFields.has(column.fieldname)"
				:field="cellFields.get(column.fieldname)!"
				:row="row"
			/>
			<div v-else class="truncate text-base text-ink-gray-8">{{ value }}</div>
		</template>
		<template v-if="rowActions.length" #rowMenu="{ row }">
			<RowMenu :options="rowMenuOptions(row, rowActions, listActs)" />
		</template>
		<template #empty>
			<PageState :name="filters.length ? 'filtered' : 'empty'" />
		</template>
	</List>
	<ListFooter
		v-model:pageSize="pageSize"
		:class="pageGutter"
		:rowCount="rowCount"
		:totalCount="totalCount"
		:totalCapped="totalCapped"
		:totalUnknown="totalUnknown"
		:hasCounts="hasCounts"
		:hasNextPage="hasNextPage"
		@load-more="next"
		@page-size="show"
		@count="countExact"
	/>

	<RowContextMenu
		v-if="menu.loaded.value"
		:at="menu.at.value"
		:rows="rows"
		:selection="selection"
		:rowMenu="(row) => rowMenuOptions(row, rowActions, listActs)"
		:bulk="bulk"
		:rowLink="rowLink"
		@close="menu.close"
	/>
	<component
		:is="bulk.parts.value.chunk.PrintDialog"
		v-if="bulk.parts.value?.print.mounted.value"
		v-model="bulk.parts.value.print.open.value"
		:doctype="view.doctype"
		:count="bulk.parts.value.print.count.value"
		:all="bulk.parts.value.print.all.value"
		:approx="bulk.parts.value.print.approx.value"
		:scope="bulk.parts.value.print.scope.value"
	/>
	<component
		:is="bulk.parts.value.chunk.EditDialog"
		v-if="editOpened && bulk.parts.value"
		v-model="editing"
		:doctype="view.doctype"
		:count="scope.count.value"
		:all="scope.all.value"
		:approx="scope.approx.value"
		:run="editSelection"
	/>
	<component
		:is="bulk.parts.value.chunk.ExportDialog"
		v-if="exportOpened && bulk.parts.value"
		v-model="exporting"
		:doctype="view.doctype"
		:selection="exportScope"
		:count="scope.count.value"
	/>
	<component
		:is="bulk.parts.value.CollabDialog"
		v-if="bulk.parts.value?.collab.request.value"
		:request="bulk.parts.value.collab.request.value"
		:doctype="view.doctype"
		:reload="reload"
		:select="(names: string[]) => (selection = names)"
		@close="bulk.parts.value.collab.request.value = null"
	/>

	<component
		:is="bulk.parts.value.chunk.DeleteDialog"
		v-if="deleteOpened && bulk.parts.value"
		v-model="confirmingDelete"
		:count="scope.count.value"
		:all="scope.all.value"
		:approx="scope.approx.value"
		:run="deleteSelection"
	/>
</template>

<script setup lang="ts">
import { ColumnSettings } from "@framework/ui/ColumnSettings";
import { LinkMark, LinkTitlesKey, isEmailField, isPhoneField } from "@framework/ui/fields";
import type { FieldMeta } from "@framework/ui/fields/types";
import { mapField, type RawMetaField } from "@framework/ui/FormLayout";
import { List, ListFooter } from "@framework/ui/experimental/List";
import { useDoctypeMeta } from "@framework/ui/useDoctypeMeta";
import { toast } from "frappe-ui";
import type { BulkSelection, BulkUpdate } from "@framework/ui/api";
import { computed, provide, ref } from "vue";
import { __, __n } from "@/i18n";
import { errorMessage } from "@/recordPage/errorMessage";
import { useListView } from "@/list/useListView";
import { useScrollMemory } from "@/list/useScrollMemory";
import type { View } from "@/list/view";
import { pageGutter } from "@/shell/PageFrame.vue";
import { failedState } from "@/shell/pageState";
import PageState from "@/shell/PageState.vue";
import AvatarStackCell from "./AvatarStackCell.vue";
import CommentsCell from "./CommentsCell.vue";
import ConfiguredCell from "./ConfiguredCell.vue";
import DocstatusCell from "./DocstatusCell.vue";
import FavouriteCell from "./FavouriteCell.vue";
import SwitchCell from "./SwitchCell.vue";
import TagsCell from "./TagsCell.vue";
import EmailCell from "./EmailCell.vue";
import FieldCell from "./FieldCell.vue";
import PhoneCell from "./PhoneCell.vue";
import type { RendererHost } from "./renderer";
import StatusCell from "./StatusCell.vue";
import RowMenu from "./RowMenu.vue";
import { rowMenuOptions } from "./rowActions";
import { useBulkBar } from "./useBulkBar";
import { RowContextMenu, useRowContextMenu } from "./useRowContextMenu";

const props = defineProps<{ view: View; host: RendererHost }>();
const { filters, sort } = props.view;

const {
	columns,
	shownColumns,
	rowActions,
	fieldOf,
	markOf,
	statusThemeOf,
	cellViewOf,
	applyBadgeFilters,
	switchOf,
	canWrite,
	currencyOf,
	linkTitles,
	seenClassOf,
	selection,
	scope,
	pageSize,
	rowsKey,
	rows,
	readFields: rowFields,
	loading,
	error,
	rowCount,
	totalCount,
	totalCapped,
	totalUnknown,
	hasCounts,
	hasNextPage,
	next,
	show,
	countExact,
	columnsCustomized,
	resetColumns,
	resizeColumn,
	resetColumnWidth,
	rowLink,
	reload,
	deleteSelection,
} = useListView(props.view, props.host.lists);

props.host.onCreate(reload);

// A Link cell shows its target's title for the name, as the record's read-only field does.
provide(LinkTitlesKey, linkTitles);

const { meta } = useDoctypeMeta(props.view.doctype);
const table = ref<{
	viewportElement: HTMLElement | null;
	toggle: (name: string) => void;
	extendTo: (name: string) => void;
} | null>(null);
const cursor = ref<string | null>(null);
const editing = ref(false);
const editOpened = ref(false);
const exporting = ref(false);
const exportOpened = ref(false);
// The export is a download of the selection as it was when it was asked for.
const exportScope = ref<BulkSelection>({ names: [] });
const confirmingDelete = ref(false);
const deleteOpened = ref(false);

useScrollMemory(
	() => table.value?.viewportElement ?? null,
	() => rows.value.length > 0,
	{ doctype: props.view.doctype, query: rowsKey }
);

const phoneFields = computed(() => columnFields(isPhoneField));
const emailFields = computed(() => columnFields(isEmailField));

// A Currency cell reads its currency from the row alone: `options` becomes the key it arrives under.
const cellFields = computed(() => {
	const fields = new Map<string, FieldMeta>();
	for (const [fieldname, field] of columnFields(() => true)) {
		const cellField = mapField(field, {});
		if (cellField.fieldtype === "Currency") cellField.options = currencyOf(fieldname)?.key;
		fields.set(fieldname, cellField);
	}
	return fields;
});

function markedText(row: Record<string, unknown>, fieldname: string): string {
	const value = String(row[fieldname] ?? "");
	const field = fieldOf(fieldname);
	if (field?.fieldtype !== "Link") return value;
	return linkTitles.value[`${field.options}::${value}`] || value;
}

function columnFields(matches: (field: RawMetaField) => boolean) {
	const fields = new Map<string, RawMetaField>();
	for (const { fieldname } of shownColumns.value) {
		const field = fieldOf(fieldname);
		if (field && matches(field)) fields.set(fieldname, field);
	}
	return fields;
}

async function editSelection(update: BulkUpdate) {
	const { updateRows } = await import("@/list/bulkEdit");
	await updateRows(props.view.doctype, { reload }, scope.selected(), update, (names) => {
		scope.clear();
		selection.value = names;
	});
	scope.clear();
}

function copySelection() {
	const names = [...selection.value];
	const chosen = new Set(names);
	const loaded = rows.value.filter((row) => chosen.has(row.name));
	const columns = shownColumns.value.map(({ fieldname, label }) => ({
		fieldname,
		label: label ?? fieldname,
	}));
	let copied = loaded.length;
	const tsv = (picked: Record<string, unknown>[]) => {
		copied = picked.length;
		return bulk.parts.value!.chunk.selectionTsv(columns, picked, markedText);
	};
	let readError: unknown;
	const withHidden = () =>
		bulk.parts
			.value!.chunk.withHiddenRows(props.view.doctype, names, loaded, rowFields())
			.then((picked) => new Blob([tsv(picked)], { type: "text/plain" }))
			.catch((error) => {
				readError = error;
				throw error;
			});
	// `navigator.clipboard` is missing on a non-secure origin; writing in the click keeps its user
	// activation, and a ClipboardItem holding a promise keeps it across the read of hidden rows.
	Promise.resolve()
		.then(() =>
			loaded.length === names.length
				? navigator.clipboard.writeText(tsv(loaded))
				: navigator.clipboard.write([new ClipboardItem({ "text/plain": withHidden() })])
		)
		.then(() => toast.success(__n("Copied {0} row", "Copied {0} rows", copied, [copied])))
		.catch(() =>
			toast.error(
				readError ? errorMessage(readError) : __("The browser did not allow copying.")
			)
		);
}

const bulk = useBulkBar({
	host: props.host,
	doctype: props.view.doctype,
	meta,
	selection,
	scope,
	rows,
	rowActions,
	reload,
	cursor,
	table: () => table.value,
	askEdit: () => {
		editOpened.value = true;
		editing.value = true;
	},
	askExport: () => {
		exportScope.value = scope.selected();
		exportOpened.value = true;
		exporting.value = true;
	},
	copy: copySelection,
	askDelete: () => {
		deleteOpened.value = true;
		confirmingDelete.value = true;
	},
});
const { listActs } = bulk;
const menu = useRowContextMenu(selection);
</script>
