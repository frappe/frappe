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

	<DeleteDialog v-model="confirmingDelete" :count="1" :run="() => deleteOne(target)" />
</template>

<script setup lang="ts">
import { ListFooter } from "@framework/ui/experimental/List";
import { useDoctypeMeta } from "@framework/ui/useDoctypeMeta";
import { Skeleton } from "frappe-ui";
import { computed, ref } from "vue";
import { __ } from "@/i18n";
import type { ListRow } from "@/list/useListRows";
import type { View } from "@/list/view";
import DeleteDialog from "@/pages/list/DeleteDialog.vue";
import type { RendererHost } from "@/pages/list/renderer";
import { rowActionEntries, rowMenuOptions } from "@/pages/list/rowActions";
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

const listActs = props.host.acts(
	() => [deleteEntry(), ...rowActionEntries(rowActions.value)],
	{ rows: () => rows.value, selection: () => [], reload }
);

function deleteEntry() {
	return {
		item: {
			name: "delete",
			label: __("Delete"),
			icon: "lucide-trash-2",
			right: "delete",
			run: (_context: unknown, row: ListRow) => {
				target.value = row.name;
				confirmingDelete.value = true;
			},
		},
		hidden: false,
	};
}

function menuFor(row: ListRow) {
	const options = rowMenuOptions(row, rowActions.value, listActs);
	const del = listActs.drawn("delete");
	return del
		? [
				...options,
				{ label: del.label!, icon: del.icon, onClick: () => listActs.perform(del, row) },
		  ]
		: options;
}
</script>
