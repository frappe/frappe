<!--
  One view of a doctype in the frame: the crumbs, the star and Create, the quick filter and the
  controls in one row under them, then the view's type's renderer in the rows area.
-->
<template>
	<PageFrame :scroll="false" :state="metaError ? failedState(metaError, reloadMeta) : null">
		<template #aboveHeader>
			<FrameBands :bands="frame.before" :page="list.page" />
		</template>

		<!-- No slot when a script emptied or hid the row: the frame then draws no row at all. -->
		<template v-if="frame.header && !isEmptyHeader(header)" #header>
			<RecordHeader
				:class="{ invisible: !list.engine.ready.value }"
				:projection="header"
				:page="list.page"
				:favourited="favourited"
				@run="runHeaderItem"
			/>
		</template>

		<FrameBands :bands="frame.between" :page="list.page" />

		<BodyColumns
			v-if="frame.body"
			kind="list"
			:items="bodyItems"
			:page="list.page"
			:user="boot.session.user.name"
		>
			<template #list>
				<!-- The column's scroller is a block: this gives the rows area a height to fill. -->
				<div class="flex h-full min-h-0 flex-col">
					<div
						v-show="!selecting"
						:class="[pageGutter, { invisible: !list.engine.ready.value }]"
						class="flex shrink-0 items-start justify-between gap-2 pt-3.5"
					>
						<div class="flex min-w-0 flex-1 flex-col">
							<QuickFilter
								v-if="shown.has('quick_filter')"
								v-model:filters="filters"
								v-model:fields="quickFilterFields"
								v-model:customizing="customizing"
								:doctype="doctype"
							/>
						</div>
						<div v-if="!customizing" class="flex shrink-0 items-center gap-2">
							<template v-for="item in rowControls" :key="item.name">
								<Filter
									v-if="item.name === 'filter'"
									v-model="filters"
									:doctype="doctype"
								/>
								<template v-else-if="item.name === 'sort'">
									<SortBy v-if="seeded" v-model="sort" :doctype="doctype" />
									<!-- Sized to the default sort: a direction button joined to its field's label. -->
									<Skeleton
										v-else
										class="h-7 w-36 shrink-0 rounded-4"
										data-sort-skeleton
									/>
								</template>
								<div
									v-else-if="item.name === 'columns'"
									:ref="setControls"
									class="contents"
								/>
								<Button
									v-else-if="scriptAct(item.name)"
									:icon-left="scriptAct(item.name)!.icon"
									:label="scriptAct(item.name)!.label"
									@click="listActs.perform(scriptAct(item.name)!)"
								/>
							</template>
							<Dropdown
								v-if="menuOptions.length"
								:options="menuOptions"
								side="bottom"
								align="end"
							>
								<div class="flex shrink-0">
									<Button icon="lucide-ellipsis" label="More" />
								</div>
							</Dropdown>
						</div>
					</div>

					<div
						v-show="selecting"
						:ref="setBar"
						:class="pageGutter"
						class="shrink-0 pt-3.5"
					/>

					<div class="relative flex min-h-0 flex-1 flex-col pt-2">
						<component
							:is="rendererFor(view.type)"
							v-if="list.engine.ready.value"
							:view="view"
							:host="host"
						/>
					</div>
				</div>
			</template>
		</BodyColumns>

		<FrameBands :bands="frame.after" :page="list.page" />
	</PageFrame>
</template>

<script setup lang="ts">
import { Button, Dropdown, Skeleton, toast } from "frappe-ui";
import { Filter } from "@framework/ui/Filter";
import { QuickFilter } from "@framework/ui/QuickFilter";
import { SortBy } from "@framework/ui/SortBy";
import { useDoctypeMeta } from "@framework/ui/useDoctypeMeta";
import { computed, inject, onMounted, onUnmounted, ref, watch } from "vue";
import { useRouter } from "vue-router";
import { passesRight, passesWhen } from "@/acts/dispatcher";
import type { Addresses } from "@/addresses";
import { isEmptyHeader, projectFrame } from "@/pageEngine";
import type { HeaderItem } from "@/pageEngine/types";
import type { Boot } from "@/boot";
import { __ } from "@/i18n";
import { isModular, routeFor, routeForModule } from "@/router/routeFor";
import { openCreate } from "@/shell/create";
import type { ListPage } from "@/list/useListPage";
import { createListPage } from "@/listPage/createListPage";
import { useListPermissions } from "@/listPage/listPermissions";
import { isFavourite, useListSettings } from "@/list/useListSettings";
import BodyColumns from "@/pages/record/body/BodyColumns.vue";
import FrameBands from "@/pages/record/FrameBands.vue";
import RecordHeader from "@/pages/record/RecordHeader.vue";
import { errorMessage } from "@/recordPage/errorMessage";
import { recordDialogWrite } from "@/shell/recordDialog";
import PageFrame, { pageGutter } from "@/shell/PageFrame.vue";
import { failedState } from "@/shell/pageState";
import { LIST_PAGE_TIER } from "@/recordPage/clientScriptTypes";
import { useLiveClientScripts } from "@/pages/record/liveClientScripts";
import { createdMessage } from "./createdMessage";
import { clearDefaultView, setDefaultView } from "./defaultView";
import { useListActs } from "./listActs";
import { listHeaderItems, projectListHeader } from "./listHeader";
import { rendererFor, type RendererHost } from "./renderer";

const props = defineProps<{ page: ListPage; label?: string }>();

const router = useRouter();
const boot = inject<Boot>("boot")!;
const addresses = inject<Addresses>("addresses")!;
const { view, quickFilterFields, customizing, metaError, reloadMeta, createValues } = props.page;
const { doctype, filters, sort, seeded } = view;

const { meta } = useDoctypeMeta(doctype);
const created: (() => void)[] = [];
let creating = false;

async function create() {
	if (creating) return;
	creating = true;
	const doc = await openCreate(doctype, { values: createValues.value }).finally(
		() => (creating = false)
	);
	if (!doc) return;
	for (const callback of created) callback();
	toast.success(createdMessage(doctype, meta.value, doc), {
		action: {
			label: __("Open"),
			onClick: () => router.push(routeFor(doctype, doc.name)),
		},
	});
}

// A record dialog over the list changed a row: the rows reload as after a Create.
watch(recordDialogWrite, (write) => {
	if (write?.doctype === doctype) for (const callback of created) callback();
});

// The plain List view is the doctype's own star; any other view is starred by its key.
const starKey = view.key === "list" ? null : view.key;
const settings = useListSettings(doctype);
const favourited = computed(() => isFavourite(settings.favourites.value, starKey));

const permissions = useListPermissions(doctype);
const list = createListPage({
	view,
	router,
	meta: () => meta.value,
	permissions,
	scripted: boot.list_script_doctypes?.includes(doctype) ?? true,
});
list.lists.controls.provideBuiltins(() => [
	{ name: "quick_filter", label: __("Quick Filter") },
	{ name: "filter", label: __("Filter") },
	{ name: "sort", label: __("Sort") },
	{ name: "columns", label: __("Columns") },
	{ name: "customize_quick_filter", label: __("Customize Quick Filter") },
]);
onMounted(list.paint);
onUnmounted(list.leave);
// A list holds no unsaved edits, so a changed List Page Client Script re-runs at once.
useLiveClientScripts({
	doctype: ref(doctype),
	tier: LIST_PAGE_TIER,
	dirty: () => false,
	ready: () => list.engine.ready.value,
	replaying: () => list.engine.isReplaying.value,
	refresh: () => list.engine.refresh(),
});

const listActs = useListActs(
	{
		list,
		permissions,
		create,
		customizeQuickFilter: () => (customizing.value = true),
		customizing: () => customizing.value,
		starsLoaded: () => settings.favourites.value !== null,
		favourited: () => favourited.value,
		toggleFavourite: () => settings.toggleFavourite(starKey),
		openView: (key) => router.push(routeFor(doctype, null, { view: key })),
		setDefaultView: (key, scope) => setDefaultView(boot, doctype, key, scope),
		clearDefaultView: (scope) => clearDefaultView(boot, doctype, scope),
	},
	view.type
);

const controls = ref<HTMLElement | null>(null);
// A function ref: a plain `ref` inside the `v-for` would collect an array.
const setControls = (element: unknown) => void (controls.value = element as HTMLElement | null);
const bar = ref<HTMLElement | null>(null);
const setBar = (element: unknown) => void (bar.value = element as HTMLElement | null);
const selecting = ref(false);
const host: RendererHost = {
	controls,
	bar,
	selecting,
	lists: list.lists,
	acts: listActs.renderer,
	onCreate: (callback) => created.push(callback),
};

const quickFilterAct = computed(() => listActs.drawn("customize_quick_filter"));

list.engine.header.provideBuiltins(() =>
	listHeaderItems({
		doctype,
		module: moduleCrumb,
		view: viewCrumb,
		starsLoaded: () => settings.favourites.value !== null,
		favourited: () => favourited.value,
		toggleFavourite: () => settings.toggleFavourite(starKey),
		create,
	})
);

function moduleCrumb() {
	const label = meta.value?.module;
	if (!label) return null;
	const slug = isModular(boot) ? addresses.addressOf(doctype)?.[1] : undefined;
	return { label, href: slug ? router.resolve(routeForModule(slug)).path : undefined };
}

function viewCrumb() {
	if (!props.label) return null;
	return { label: props.label, href: router.resolve(routeFor(doctype)).path };
}

const scope = {
	context: () => list.page,
	passes: permissions.passes,
	settled: () => (permissions.loading() ? permissions.ready() : undefined),
};
const allows = (item: HeaderItem) => passesWhen(scope, item) && passesRight(scope, item);
const header = computed(() => projectListHeader(list.engine.header.resolve(), allows));
const frame = computed(() => projectFrame(list.engine.frame.resolve()));
const bodyItems = computed(() => list.engine.body.visible());

// A header item runs as an act, inside a hold so its ops paint once; a throw is a toast.
function runHeaderItem(item: HeaderItem) {
	void list.engine
		.hold(() => item.run?.(list.page))
		.catch((error) => void toast.error(errorMessage(error)));
}

const controlItems = computed(() => list.lists.controls.visible());
const shown = computed(() => new Set(controlItems.value.map((item) => item.name)));
const rowControls = computed(() =>
	controlItems.value.filter(
		(item) => !["quick_filter", "customize_quick_filter"].includes(item.name)
	)
);
const scriptAct = (name: string) => listActs.drawn(name);

const menuOptions = computed(() => {
	const act = quickFilterAct.value;
	if (!act || !shown.value.has("customize_quick_filter") || !shown.value.has("quick_filter"))
		return [];
	return [{ label: act.label, icon: act.icon, onClick: () => listActs.perform(act) }];
});
</script>
