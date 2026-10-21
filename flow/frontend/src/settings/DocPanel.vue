<template>
	<DocForm
		v-if="mode === 'form'"
		:spec="spec"
		:name="editing"
		:title="editing ? `Edit ${spec.singular}` : `New ${spec.singular}`"
		:back="`Back to ${spec.label.toLowerCase()}`"
		@saved="saved"
		@deleted="changed"
		@close="mode = 'list'"
	/>
	<SettingsPage v-else :title="title || spec.label" :description="description">
		<slot name="tabs" />
		<!-- a narrow frame's search fills the row beside the button; a filter takes a row of its own -->
		<div class="mb-3 flex flex-wrap items-center gap-2 pt-1">
			<FormControl
				v-model="query"
				type="text"
				variant="outline"
				placeholder="Search"
				class="w-56 max-md:min-w-0 max-md:flex-1"
			/>
			<slot name="filters" />
			<span class="flex-1 max-md:hidden" />
			<Button
				v-if="canCreate"
				variant="solid"
				:label="`New ${spec.singular}`"
				@click="edit(null)"
			/>
		</div>
		<LoadingState
			v-if="loading && !loaded"
			class="justify-center py-8 text-xs text-ink-gray-5"
		/>
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
import { computed, inject, ref } from "vue";
import { Badge, Button, ErrorMessage, FormControl } from "frappe-ui";
import LoadingState from "@flow/ui-core/components/LoadingState.vue";
import SettingsPage from "@flow/ui-core/components/SettingsPage.vue";

import DocForm from "./DocForm.vue";
import { useRecordList } from "./records.js";

// One doctype's settings page: its list under the section heading, or one record's form
// as a page of its own.
const props = defineProps({
	spec: { type: Object, required: true },
	filters: { type: Object, default: () => ({}) },
	title: { type: String, default: "" }, // the section heading; the spec's label by default
	description: { type: String, default: "" },
});
const page = inject("flowPage");

// a blank record when one was asked for from outside settings ("Add a model"), else the list
const mode = ref(page.takeNewRecord(props.spec.key) ? "form" : "list");
const editing = ref(null);
const query = ref("");
const canCreate = computed(() => page.can(props.spec.doctype, "create"));
const { rows, loaded, loading, error, hasMore, hasEnabled, load, drop } = useRecordList(
	props.spec,
	{ query, filters: () => props.filters }
);

function edit(name) {
	editing.value = name;
	mode.value = "form";
}

// a save stays on the form, now editing the saved record
function saved(doc) {
	editing.value = doc.name;
	load();
}

function changed() {
	mode.value = "list";
	drop(editing.value);
}
</script>
