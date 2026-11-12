<!-- The Cards type's renderer: a grid of cards, the List's footer, and the card settings among the controls. -->
<template>
	<Teleport v-if="host.bar.value && selection.length" :to="host.bar.value">
		<BulkBar
			:scope="scope"
			:cap="bulk.cap"
			:layout="bulk.layout.value"
			:locked="bulk.locked"
			@clear="scope.clear()"
		/>
	</Teleport>
	<Teleport v-if="host.controls.value" :to="host.controls.value">
		<CardSettings
			:meta="meta"
			:title="fields.title"
			:body="fields.body"
			:update="view.update"
		/>
	</Teleport>
	<PageState v-if="error" v-bind="failedState(error, reload)" />
	<div v-else class="min-h-0 flex-1 overflow-y-auto py-2" :class="pageGutter">
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
				@toggle="toggle(row.name)"
			/>
		</div>
	</div>
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

	<DeleteDialog
		v-model="confirmingDelete"
		:count="target ? 1 : scope.count.value"
		:all="!target && scope.all.value"
		:approx="!target && scope.approx.value"
		:run="() => (target ? deleteOne(target) : deleteSelection())"
	/>
</template>

<script setup lang="ts">
import { ListFooter } from "@framework/ui/experimental/List";
import { useDoctypeMeta } from "@framework/ui/useDoctypeMeta";
import { Skeleton } from "frappe-ui";
import { onScopeDispose, ref, watchEffect } from "vue";
import { __ } from "@/i18n";
import type { ListRow } from "@/list/useListRows";
import type { View } from "@/list/view";
import BulkBar from "@/pages/list/BulkBar.vue";
import DeleteDialog from "@/pages/list/DeleteDialog.vue";
import type { RendererHost } from "@/pages/list/renderer";
import { rowMenuOptions } from "@/pages/list/rowActions";
import { useBulkBar } from "@/pages/list/useBulkBar";
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

// The bulk delete is the surface's `delete`; a card's own menu runs `delete_card` on that card.
const bulk = useBulkBar({
	host: props.host,
	doctype: props.view.doctype,
	selection,
	scope,
	rows,
	rowActions,
	reload,
	askDelete: () => ask(""),
	extraEntries: () => [deleteCardEntry()],
});
const { listActs } = bulk;

// The page swaps its controls row for the bar while this is true.
watchEffect(() => (props.host.selecting.value = selection.value.length > 0));
onScopeDispose(() => (props.host.selecting.value = false));

function ask(name: string) {
	target.value = name;
	confirmingDelete.value = true;
}

function toggle(name: string) {
	selection.value = selection.value.includes(name)
		? selection.value.filter((key) => key !== name)
		: [...selection.value, name];
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

function menuFor(row: ListRow) {
	const options = rowMenuOptions(row, rowActions.value, listActs);
	const del = listActs.drawn("delete_card");
	return del
		? [
				...options,
				{ label: del.label!, icon: del.icon, onClick: () => listActs.perform(del, row) },
		  ]
		: options;
}
</script>
