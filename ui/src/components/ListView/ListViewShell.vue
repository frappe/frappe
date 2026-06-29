<!--
  Composite List View "shell" — the integration surface the extracted controls
  mount into. For now it owns no view state and renders only placeholder chrome:
  a toolbar region (where SortBy/Filter/ColumnSettings/QuickFilter will land) and
  a table chrome region. Its job today is to prove the cross-repo wiring — alias
  resolution, live `useDoctypeMeta` fetch, route mount — before any control exists.

  Hosts pass a `doctype`; the shell resolves its Meta and exposes a `#toolbar`
  slot (the controls' future home) plus a `#table` slot. The default table slot
  renders the doctype's fields as placeholder column headers so a visitor can see
  that meta resolved.
-->
<template>
	<div class="flex flex-col rounded-lg border border-outline-gray-1 bg-surface-white">
		<!-- Toolbar region: the future home of the list-view controls. -->
		<div class="flex items-center gap-2 border-b border-outline-gray-1 px-3 py-2">
			<div class="text-base font-medium text-ink-gray-8">{{ title }}</div>
			<div class="flex flex-1 items-center justify-end gap-2">
				<slot name="toolbar" :doctype="doctype" :meta="meta" :loading="loading" />
			</div>
		</div>

		<!-- Table chrome region. -->
		<div class="min-h-32 p-3">
			<div v-if="loading" class="text-p-sm text-ink-gray-5">Loading meta…</div>
			<div v-else-if="errorMessage" class="text-p-sm text-ink-red-4">
				{{ errorMessage }}
			</div>
			<slot v-else name="table" :doctype="doctype" :meta="meta">
				<!-- Default placeholder table: column headers from meta, no rows. -->
				<div
					class="flex items-center gap-4 border-b border-outline-gray-1 pb-2 text-p-sm font-medium text-ink-gray-6"
				>
					<span v-for="field in columnFields" :key="field.fieldname" class="truncate">
						{{ field.label || field.fieldname }}
					</span>
				</div>
				<div class="flex h-24 items-center justify-center text-p-sm text-ink-gray-4">
					{{ fieldCount }} fields in meta
				</div>
			</slot>
		</div>
	</div>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { useDoctypeMeta } from "../../composables/useDoctypeMeta";
import type { RawMetaField } from "../FormLayout/types";

const props = defineProps<{ doctype: string }>();

const { meta, loading, error } = useDoctypeMeta(props.doctype);

const title = computed(() => meta.value?.name ?? props.doctype);

const fields = computed<RawMetaField[]>(() => meta.value?.fields ?? []);
const fieldCount = computed(() => fields.value.length);

// A handful of "in list view" fields to stand in for real columns. Falls back to
// the first few labelled fields if none are flagged, so the placeholder is never
// empty for doctypes that don't set `in_list_view`.
const columnFields = computed<RawMetaField[]>(() => {
	const inList = fields.value.filter((f) => f.in_list_view && f.label);
	const picked = inList.length ? inList : fields.value.filter((f) => f.label);
	return picked.slice(0, 6);
});

const errorMessage = computed(() =>
	error.value ? (error.value instanceof Error ? error.value.message : String(error.value)) : ""
);
</script>
