<!-- The Cards type's renderer: a grid of cards, the List's footer, and the card settings among the controls. -->
<template>
	<Teleport v-if="host.controls.value" :to="host.controls.value">
		<CardSettings
			:meta="meta"
			:title="fields.title"
			:body="fields.body"
			:update="view.update"
		/>
	</Teleport>
	<PageState v-if="error" v-bind="failedState(error, reload)" />
	<div
		v-else
		class="min-h-0 flex-1 overflow-y-auto py-2"
		:class="[pageGutter, selection.length && 'pb-[4.5rem]']"
		@pointerover="bulk.prefetch"
		@focusin="bulk.prefetch"
	>
		<div v-if="loading" :style="gridStyle" class="grid">
			<Skeleton v-for="n in 8" :key="n" class="h-56 rounded-5" />
		</div>
		<PageState v-else-if="!rows.length" :name="filters.length ? 'filtered' : 'empty'" />
		<div v-else :style="gridStyle" class="grid">
			<CardItem
				v-for="row in rows"
				:key="row.name"
				:row="row"
				:meta="meta"
				:titleField="fields.title"
				:bodyField="fields.body"
				:bodyIsHtml="fields.bodyIsHtml"
				:link="cardLink(row)"
				:titleClass="titleClassOf(row)"
				:menu="menuFor(row)"
				:person="people[String(row.owner)]"
				:selected="selection.includes(row.name)"
				:selecting="selection.length > 0"
				@toggle="toggle(row.name, $event)"
				@contextmenu="menu.open(row.name, $event)"
				@pointerenter="enter(row.name)"
				@pointerleave="leave(row.name)"
				@focusin="focus(row.name)"
				@focusout="blur(row.name)"
			/>
		</div>
	</div>
	<component
		:is="bulk.parts.value.chunk.BulkIsland"
		v-if="bulk.parts.value"
		:open="selection.length > 0"
		:scope="scope"
		:doctype="view.doctype"
		:status="bulk.parts.value.status"
		:cap="bulk.cap"
		:layout="bulk.layout.value"
		:locked="bulk.locked"
		v-model:menuOpen="bulk.menuOpen.value"
		@clear="scope.clear()"
	/>
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
		:rowMenu="(row) => menuFor(row, bulk.locked)"
		:bulk="bulk"
		:rowLink="cardLink"
		@close="menu.close"
	/>
	<component
		:is="bulk.parts.value.chunk.BulkDialogs"
		v-if="bulk.parts.value"
		:parts="bulk.parts.value"
		:scope="scope"
		:doctype="view.doctype"
		:reload="reload"
		:select="(names: string[]) => (selection = names)"
	/>
	<DeleteDialog
		v-model="confirmingDelete"
		:count="target ? 1 : scope.count.value"
		:all="!target && scope.all.value"
		:approx="!target && scope.approx.value"
		:run="() => (target ? deleteOne(target) : deleteSelection())"
	/>
</template>

<script setup lang="ts">
import { ListFooter, useRowCursor, useRowSelection } from "@framework/ui/experimental/List";
import { useDoctypeMeta } from "@framework/ui/useDoctypeMeta";
import { Skeleton } from "frappe-ui";
import { ref } from "vue";
import { __ } from "@/i18n";
import type { ListRow } from "@/list/useListRows";
import type { View } from "@/list/view";
import DeleteDialog from "@/pages/list/DeleteDialog.vue";
import type { RendererHost } from "@/pages/list/renderer";
import { rowMenuOptions } from "@/pages/list/rowActions";
import { useBulkBar } from "@/pages/list/useBulkBar";
import { RowContextMenu, useRowContextMenu } from "@/pages/list/useRowContextMenu";
import { pageGutter } from "@/shell/PageFrame.vue";
import { failedState } from "@/shell/pageState";
import PageState from "@/shell/PageState.vue";
import CardItem from "./CardItem.vue";
import CardSettings from "./CardSettings.vue";
import { useCardsView } from "./useCardsView";

const props = defineProps<{ view: View; host: RendererHost }>();
const { filters } = props.view;

const {
	fields,
	rowActions,
	people,
	pageSize,
	selection,
	scope,
	rows,
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
	reload,
	readFields,
	cardLink,
	titleClassOf,
	deleteOne,
	deleteSelection,
} = useCardsView(props.view, props.host.lists);

props.host.onCreate(reload);

const { meta } = useDoctypeMeta(props.view.doctype);
const confirmingDelete = ref(false);
const target = ref("");

// At least 240px a card and at most four a row, with the page's gap between them.
const gridStyle = {
	gap: "var(--page-gutter)",
	gridTemplateColumns:
		"repeat(auto-fill, minmax(max(240px, calc((100% - 3 * var(--page-gutter)) / 4)), 1fr))",
};

const { toggle, extendTo } = useRowSelection(selection, rows, ref("name"));
const cursor = ref<string | null>(null);
const { enter, leave, focus, blur } = useRowCursor(cursor, () =>
	rows.value.map((row) => row.name)
);

// The bulk delete is the surface's `delete`; a card's own menu runs `delete_card` on that card.
const bulk = useBulkBar({
	host: props.host,
	doctype: props.view.doctype,
	meta,
	selection,
	scope,
	rows,
	rowActions,
	reload,
	askDelete: () => ask(""),
	copy: {
		columns: copyColumns,
		text: (row, fieldname) => String(row[fieldname] ?? ""),
		fields: readFields,
	},
	cursor,
	table: () => ({ toggle, extendTo }),
	extraEntries: () => [deleteCardEntry()],
});
const { listActs } = bulk;
const menu = useRowContextMenu(selection);

function ask(name: string) {
	target.value = name;
	confirmingDelete.value = true;
}

// Copy writes what a card shows: its title and body, after the name when the title is another field.
function copyColumns() {
	const { title, body } = fields.value;
	const labelOf = (fieldname: string) =>
		meta.value?.fields?.find((field) => field.fieldname === fieldname)?.label ?? fieldname;
	return [...new Set(["name", title, ...(body ? [body] : [])])].map((fieldname) => ({
		fieldname,
		label: fieldname === "name" ? __("ID") : labelOf(fieldname),
	}));
}

function deleteCardEntry() {
	return {
		item: {
			name: "delete_card",
			label: __("Delete"),
			icon: "lucide-trash-2",
			right: "delete",
			palette: false,
			run: (_context: unknown, row: ListRow) => ask(row.name),
		},
		hidden: false,
	};
}

// The right-click menu has the bulk Delete for one card, so it takes the card's own Delete only when the bar is locked.
function menuFor(row: ListRow, ownDelete = true) {
	const options = rowMenuOptions(row, rowActions.value, listActs);
	const del = ownDelete && listActs.drawn("delete_card");
	return del
		? [
				...options,
				{ label: del.label!, icon: del.icon, onClick: () => listActs.perform(del, row) },
		  ]
		: options;
}
</script>
