<template>
	<PageHeader :icon="info.icon" :title="spec.label">
		<template v-if="canCreate" #actions>
			<Button
				variant="solid"
				icon-left="plus"
				:label="`New ${spec.singular}`"
				@click="create"
			/>
		</template>
	</PageHeader>
	<!-- the search and a menu per filter, once the list has loaded with something in it -->
	<div v-if="loaded && !empty" class="flex flex-wrap items-center gap-2 px-5 pb-3 pt-1">
		<FormControl
			v-model="query"
			type="text"
			variant="subtle"
			:placeholder="`Search ${spec.label.toLowerCase()}`"
			class="w-64 max-md:w-full"
		>
			<template #prefix>
				<span class="lucide-search size-4 text-ink-gray-5" aria-hidden="true" />
			</template>
		</FormControl>
		<Dropdown v-for="filter in filters" :key="filter.field" :options="choices(filter)">
			<template #trigger>
				<button
					class="flex h-7 items-center gap-1.5 rounded-4 px-2.5 text-sm transition-colors"
					:class="
						chosen[filter.field] === undefined
							? 'bg-surface-gray-2 text-ink-gray-7 hover:bg-surface-gray-3'
							: 'bg-surface-gray-3 text-ink-gray-9'
					"
				>
					{{ filterLabel(filter) }}
					<span
						class="lucide-chevron-down size-3.5 text-ink-gray-5"
						aria-hidden="true"
					/>
				</button>
			</template>
		</Dropdown>
		<button
			v-if="narrowed"
			class="h-7 px-1.5 text-sm text-ink-gray-5 hover:text-ink-gray-8"
			@click="clear"
		>
			Clear
		</button>
	</div>
	<div class="min-h-0 flex-1 overflow-y-auto px-5 pb-10">
		<LoadingState
			v-if="loading && !loaded"
			class="justify-center py-16 text-xs text-ink-gray-5"
		/>
		<!-- nothing yet: what the page is for, and the way to a first one -->
		<div v-else-if="empty" class="flex flex-col items-center px-6 py-16 text-center">
			<span :class="info.icon" class="size-6 text-ink-gray-4" aria-hidden="true" />
			<p class="mt-3 text-sm font-medium text-ink-gray-8">
				No {{ spec.label.toLowerCase() }} yet
			</p>
			<p class="mt-1.5 max-w-sm text-xs leading-5 text-ink-gray-5">{{ info.description }}</p>
			<Button
				v-if="canCreate"
				class="mt-4"
				icon-left="plus"
				:label="`New ${spec.singular}`"
				@click="create"
			/>
		</div>
		<div
			v-else-if="!rows.length && !error"
			class="flex flex-col items-center gap-3 py-16 text-center"
		>
			<p class="text-sm text-ink-gray-5">No {{ spec.label.toLowerCase() }} match.</p>
			<Button label="Clear filters" @click="clear" />
		</div>
		<div v-else-if="rows.length" role="table" :aria-label="spec.label">
			<!-- one line a row, every row as tall as the next; a narrow frame keeps the title and status -->
			<div
				role="row"
				class="sticky top-0 z-[1] grid h-9 items-center gap-4 border-b border-outline-gray-1 bg-surface-base px-3 text-xs text-ink-gray-5 max-md:hidden"
				:style="grid"
			>
				<span role="columnheader">Name</span>
				<span v-for="column in info.columns" :key="column.label" role="columnheader">{{
					column.label
				}}</span>
				<span role="columnheader">Status</span>
			</div>
			<RouterLink
				v-for="row in rows"
				:key="row.name"
				role="row"
				:to="{ name: 'records', params: { kind: spec.key, record: row.name } }"
				class="grid h-10 items-center gap-4 border-b border-outline-gray-1 px-3 text-sm hover:bg-surface-gray-1 max-md:h-12"
				:style="grid"
			>
				<span role="cell" class="truncate font-[450] text-ink-gray-9">{{
					row[spec.titleField] || row.name
				}}</span>
				<span
					v-for="column in info.columns"
					:key="column.label"
					role="cell"
					class="truncate text-ink-gray-6 max-md:hidden"
					>{{ column.value(row) || "—" }}</span
				>
				<span role="cell" class="flex">
					<Badge
						:theme="row.enabled ? 'green' : 'gray'"
						:label="row.enabled ? 'Enabled' : 'Disabled'"
					/>
				</span>
			</RouterLink>
		</div>
		<div v-if="error || hasMore" class="mt-3 flex items-center gap-3">
			<ErrorMessage :message="error" />
			<Button
				variant="outline"
				:label="error ? 'Retry' : 'Load more'"
				:loading="loading"
				@click="load(true)"
			/>
		</div>
	</div>
</template>

<script setup>
import { computed, h, inject, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { Badge, Button, ErrorMessage, FormControl } from "frappe-ui";
import Dropdown from "frappe-ui/src/components/Dropdown/Dropdown.vue";
import LoadingState from "@flow/ui-core/components/LoadingState.vue";
import { layout } from "@flow/ui-core/layout.js";

import { useRecordList } from "../settings/records.js";
import PageHeader from "./PageHeader.vue";
import { STATUS_FILTER } from "./pages.js";

// A page's records as a table: searched and filtered, a link to each, and the way to a new one
// for whoever may create them. The search and the filters live in the address, so Back from a
// record, or a reload, finds the list as it was.
const props = defineProps({
	spec: { type: Object, required: true },
	info: { type: Object, required: true }, // the page's entry in PAGES
});
const page = inject("flowPage");
const route = useRoute();
const router = useRouter();

const canCreate = computed(() => page.can(props.spec.doctype, "create"));
const filters = computed(() => [STATUS_FILTER, ...props.info.filters(page.state.boot)]);
const chosen = computed(() =>
	Object.fromEntries(
		filters.value
			.filter((filter) => route.query[filter.field] != null)
			.map((filter) => [filter.field, String(route.query[filter.field])])
	)
);
const query = ref(String(route.query.q ?? ""));
const { rows, loaded, loading, error, hasMore, load, debouncedQuery } = useRecordList(props.spec, {
	query,
	filters: () => chosen.value,
});
const narrowed = computed(() => !!query.value.trim() || Object.keys(chosen.value).length > 0);
// nothing to search or filter: the page's empty state instead, once a list loaded with neither
// is empty (the rows of a search being cleared are still its own)
const empty = computed(
	() =>
		loaded.value &&
		!loading.value &&
		!rows.value.length &&
		!error.value &&
		!debouncedQuery.value.trim() &&
		!Object.keys(chosen.value).length
);
watch(debouncedQuery, (text) => setQuery({ q: text.trim() || undefined }));
// and back: a link with another search, or none (the sidebar's), sets the box
watch(
	() => String(route.query.q ?? ""),
	(q) => {
		if (q !== debouncedQuery.value.trim()) query.value = q;
	}
);

const grid = computed(() => ({
	gridTemplateColumns: layout.narrow
		? "minmax(0, 1fr) auto"
		: [
				"minmax(0, 1.2fr)",
				...props.info.columns.map((column) => `minmax(0, ${column.width})`),
				"5.5rem",
		  ].join(" "),
}));

function setQuery(changes) {
	router.replace({ query: { ...route.query, ...changes } });
}

// a filter's menu: All, then its choices, the one in force ticked
const tick = () =>
	h("span", { class: "lucide-check ml-auto size-4 text-ink-gray-7", "aria-hidden": "true" });
function choices(filter) {
	const option = (label, value) => ({
		label,
		slots: chosen.value[filter.field] === value ? { suffix: tick } : {},
		onClick: () => setQuery({ [filter.field]: value }),
	});
	return [
		option("All", undefined),
		...filter.options.map((choice) => option(choice.label, choice.value)),
	];
}
function filterLabel(filter) {
	const value = chosen.value[filter.field];
	const choice = filter.options.find((option) => option.value === value);
	return value === undefined ? filter.label : `${filter.label}: ${choice?.label ?? value}`;
}
function clear() {
	query.value = "";
	router.replace({ query: {} });
}

function create() {
	router.push({ name: "records", params: { kind: props.spec.key, record: "new" } });
}
</script>
