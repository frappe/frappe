<!--
  One doctype's list in the frame: the crumbs and Create, the quick filter and the controls in one
  row under them, then the table with its bulk bar and footer. The composable holds the state; this lays it out.
-->
<template>
	<PageFrame :scroll="false" :state="metaError ? failedState(metaError, reloadMeta) : null">
		<template #header>
			<div class="flex min-w-0 flex-1 items-center justify-between gap-3">
				<div class="flex min-w-0 flex-1 items-center gap-1 text-base">
					<Breadcrumbs class="-ml-0.5" :items="crumbs" />
					<Tooltip v-if="favouriteAct" :text="favouriteAct.label">
						<FavouriteStar
							:favourited="favourited"
							@click="listActs.perform(favouriteAct)"
						/>
					</Tooltip>
				</div>
				<Button
					v-if="createAct"
					variant="solid"
					:icon-left="createAct.icon"
					:label="createAct.label"
					@click="listActs.perform(createAct)"
				/>
			</div>
		</template>

		<div :class="pageGutter" class="flex shrink-0 items-start justify-between gap-2 pt-3.5">
			<div class="flex min-w-0 flex-1 flex-col">
				<QuickFilter
					v-model:filters="filters"
					v-model:fields="quickFilterFields"
					v-model:customizing="customizing"
					:doctype="doctype"
				/>
			</div>
			<div v-if="!customizing" class="flex shrink-0 items-center gap-2">
				<Filter v-model="filters" :doctype="doctype" />
				<SortBy v-if="seeded" v-model="sort" :doctype="doctype" />
				<!-- Sized to the default sort: a direction button joined to its field's label. -->
				<Skeleton v-else class="h-7 w-36 shrink-0 rounded-4" data-sort-skeleton />
				<ColumnSettings
					v-model="columns"
					:doctype="doctype"
					:canReset="columnsCustomized"
					@reset="resetColumns"
				/>
				<Dropdown :options="menuOptions" side="bottom" align="end">
					<div class="flex shrink-0">
						<Button icon="lucide-ellipsis" label="More" />
					</div>
				</Dropdown>
			</div>
		</div>

		<div class="relative flex min-h-0 flex-1 flex-col pt-2">
			<PageState v-if="error" v-bind="failedState(error, reload)" />
			<List
				v-else
				ref="table"
				v-model:selection="selection"
				v-model:sort="sort"
				:columns="columns"
				:rows="rows"
				:loading="loading"
				:rowLink="rowLink"
				gutter="var(--page-gutter)"
				@column-resize="resizeColumn($event.fieldname, $event.width)"
				@column-reset="resetColumnWidth($event.fieldname)"
			>
				<template #empty>
					<PageState :name="filters.length ? 'filtered' : 'empty'" />
				</template>
			</List>
			<ListBulkBar v-model:selection="selection" :actions="bulkActions" />
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
		</div>

		<DeleteDialog
			v-model="confirmingDelete"
			:count="selection.length"
			:run="deleteSelection"
		/>
	</PageFrame>
</template>

<script setup lang="ts">
import { Breadcrumbs, Button, Dropdown, Skeleton, Tooltip, toast } from "frappe-ui";
import { ColumnSettings } from "@framework/ui/ColumnSettings";
import { List, ListBulkBar, ListFooter, type BulkAction } from "@framework/ui/experimental/List";
import { Filter } from "@framework/ui/Filter";
import { QuickFilter } from "@framework/ui/QuickFilter";
import { SortBy } from "@framework/ui/SortBy";
import { useDoctypeMeta } from "@framework/ui/useDoctypeMeta";
import { computed, ref } from "vue";
import { useRouter } from "vue-router";
import { __ } from "@/i18n";
import { routeFor } from "@/router/routeFor";
import { openCreate } from "@/shell/create";
import { useListPage } from "@/list/useListPage";
import { isFavourite, useListSettings } from "@/list/useListSettings";
import { useScrollMemory } from "@/list/useScrollMemory";
import FavouriteStar from "@/pages/favourite/FavouriteStar.vue";
import PageFrame, { pageGutter } from "@/shell/PageFrame.vue";
import { failedState } from "@/shell/pageState";
import PageState from "@/shell/PageState.vue";
import { createdMessage } from "./createdMessage";
import DeleteDialog from "./DeleteDialog.vue";
import { useListActs } from "./listActs";

const props = defineProps<{ doctype: string; view?: string | null; viewLabel?: string | null }>();

const router = useRouter();

const crumbs = computed(() =>
	props.viewLabel
		? [{ label: props.doctype, route: routeFor(props.doctype) }, { label: props.viewLabel }]
		: [{ label: props.doctype }]
);

const {
	filters,
	sort,
	columns,
	quickFilterFields,
	customizing,
	selection,
	pageSize,
	rowsKey,
	rows,
	loading,
	error,
	metaError,
	reloadMeta,
	seeded,
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
	createValues,
	reload,
	deleteSelection,
} = useListPage(props.doctype);

const { meta } = useDoctypeMeta(props.doctype);
let creating = false;

async function create() {
	if (creating) return;
	creating = true;
	const doc = await openCreate(props.doctype, { values: createValues.value }).finally(
		() => (creating = false)
	);
	if (!doc) return;
	reload();
	toast.success(createdMessage(props.doctype, meta.value, doc), {
		action: {
			label: __("Open"),
			onClick: () => router.push(routeFor(props.doctype, doc.name)),
		},
	});
}

const table = ref<{ viewportElement: HTMLElement | null } | null>(null);
const confirmingDelete = ref(false);

useScrollMemory(
	() => table.value?.viewportElement ?? null,
	() => rows.value.length > 0,
	{ doctype: props.doctype, query: rowsKey }
);

const settings = useListSettings(props.doctype);
const favourited = computed(() => isFavourite(settings.favourites.value, props.view ?? null));

const listActs = useListActs({
	doctype: props.doctype,
	create,
	customizeQuickFilter: () => (customizing.value = true),
	confirmDelete: () => (confirmingDelete.value = true),
	customizing: () => customizing.value,
	selected: () => selection.value.length,
	starsLoaded: () => settings.favourites.value !== null,
	favourited: () => favourited.value,
	toggleFavourite: () => settings.toggleFavourite(props.view ?? null),
	openView: (key) => router.push(routeFor(props.doctype, null, { view: key })),
});

const createAct = computed(() => listActs.drawn("create"));
const favouriteAct = computed(() => listActs.drawn("favourite"));
const quickFilterAct = computed(() => listActs.drawn("customize_quick_filter"));
const deleteAct = computed(() => listActs.drawn("delete"));

const menuOptions = computed(() => {
	const act = quickFilterAct.value;
	return act ? [{ label: act.label, icon: act.icon, onClick: () => listActs.perform(act) }] : [];
});

const bulkActions = computed<BulkAction[]>(() => {
	const act = deleteAct.value;
	return act ? [{ label: act.label!, theme: "red", onClick: () => listActs.perform(act) }] : [];
});
</script>
