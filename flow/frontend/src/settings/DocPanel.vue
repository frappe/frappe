<template>
	<DocForm
		v-if="mode === 'form'"
		:spec="spec"
		:name="editing"
		:title="editing ? `Edit ${spec.singular}` : `New ${spec.singular}`"
		:back="`Back to ${spec.label.toLowerCase()}`"
		@saved="changed"
		@deleted="changed"
		@close="mode = 'list'"
	/>
	<SettingsPage v-else :title="title || spec.label" :description="description">
		<slot name="tabs" />
		<div class="mb-3 flex flex-wrap items-center gap-2 pt-1">
			<FormControl
				v-model="query"
				type="text"
				variant="outline"
				placeholder="Search"
				class="w-56"
			/>
			<slot name="filters" />
			<span class="flex-1" />
			<Button
				v-if="canCreate"
				variant="solid"
				:label="`New ${spec.singular}`"
				@click="edit(null)"
			/>
		</div>
		<div v-if="loading && !rows.length" class="py-8 text-center text-xs text-ink-gray-5">
			Loading…
		</div>
		<div
			v-else-if="!rows.length && !error"
			class="rounded-6 border border-dashed border-outline-gray-2 py-10 text-center text-xs text-ink-gray-5"
		>
			No {{ spec.label.toLowerCase() }} yet.
		</div>
		<ul
			v-else
			class="divide-y divide-outline-gray-1 overflow-hidden rounded-6 border border-outline-gray-2"
		>
			<li v-for="row in rows" :key="row.name">
				<button
					class="flex w-full items-center gap-3 px-3 py-2.5 text-left hover:bg-surface-gray-1"
					@click="edit(row.name)"
				>
					<span class="min-w-0 flex-1">
						<span class="block truncate text-sm font-medium text-ink-gray-9">{{
							row[spec.titleField] || row.name
						}}</span>
						<span
							v-if="spec.subtitle?.(row)"
							class="mt-1 block truncate text-2xs text-ink-gray-5"
							>{{ spec.subtitle(row) }}</span
						>
					</span>
					<Badge
						v-if="hasEnabled"
						:theme="row.enabled ? 'green' : 'gray'"
						:label="row.enabled ? 'Enabled' : 'Disabled'"
					/>
				</button>
			</li>
		</ul>
		<ErrorMessage :message="error" class="mt-3" />
		<Button
			v-if="hasMore || error"
			class="mt-3"
			variant="outline"
			:label="error ? 'Retry' : 'Load more'"
			:loading="loading"
			@click="load(true)"
		/>
	</SettingsPage>
</template>

<script setup>
import { computed, inject, onBeforeUnmount, ref, watch } from "vue";
import { Badge, Button, ErrorMessage, FormControl } from "frappe-ui";
import { useDebouncedValue } from "@flow/ui-core/debounce.js";
import SettingsPage from "@flow/ui-core/components/SettingsPage.vue";

import DocForm from "./DocForm.vue";
import { call } from "../api/frappe.js";

// One doctype's settings page: its list under the section heading, or one record's form
// as a page of its own.
const props = defineProps({
	spec: { type: Object, required: true },
	filters: { type: Object, default: () => ({}) },
	title: { type: String, default: "" }, // the section heading; the spec's label by default
	description: { type: String, default: "" },
});
const page = inject("flowPage");

const mode = ref("list");
const editing = ref(null);
const query = ref("");
const debouncedQuery = useDebouncedValue(query, 150);
const canCreate = computed(() => page.can(props.spec.doctype, "create"));
const hasEnabled = props.spec.fields.some((field) => field.name === "enabled");

const PAGE_LENGTH = 200;
const rows = ref([]);
const loading = ref(false);
const error = ref("");
const hasMore = ref(false);
let request = 0;

watch([debouncedQuery, () => props.filters], () => load(), { deep: true, immediate: true });
onBeforeUnmount(() => request++);

async function load(append = false) {
	if (append && loading.value) return;
	const own = ++request;
	if (!append) rows.value = [];
	loading.value = true;
	error.value = "";
	const query = debouncedQuery.value.trim().replace(/[\\%_]/g, "\\$&");
	try {
		const data = await call("frappe.client.get_list", {
			doctype: props.spec.doctype,
			fields: hasEnabled ? [...props.spec.listFields, "enabled"] : props.spec.listFields,
			filters: props.filters,
			or_filters: query
				? props.spec.listFields.map((field) => [field, "like", `%${query}%`])
				: [],
			order_by: `${props.spec.orderBy ?? `${props.spec.titleField} asc`}, name asc`,
			limit_start: rows.value.length,
			limit_page_length: PAGE_LENGTH + 1,
		});
		if (own !== request) return;
		hasMore.value = data.length > PAGE_LENGTH;
		rows.value.push(...data.slice(0, PAGE_LENGTH));
	} catch (err) {
		if (own === request) error.value = err.message;
	} finally {
		if (own === request) loading.value = false;
	}
}

function edit(name) {
	editing.value = name;
	mode.value = "form";
}

function changed() {
	mode.value = "list";
	load();
}
</script>
