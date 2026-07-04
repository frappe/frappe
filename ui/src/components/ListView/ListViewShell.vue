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
	<!-- Bounded flex column so only the rows scroll (CRM-parity): the toolbar and
	     footer are fixed (`shrink-0`), the table region takes the remaining height
	     (`flex-1 min-h-0`), and the list's own `ListRows` (`overflow-y-auto`) is the
	     sole scroller. Needs a height from the parent (the story gives it `flex-1`);
	     `min-h-0` lets it shrink, `overflow-hidden` clips so nothing spills the card. -->
	<div
		class="flex min-h-0 flex-col overflow-hidden rounded-lg border border-outline-gray-1 bg-surface-white"
	>
		<!-- Toolbar region: the home of the list-view controls. The slotted content
		     owns its own alignment (quick filters left, Filter/Sort right). -->
		<!-- `items-start` so Filter/Sort stay pinned to the top row when the quick
		     filters wrap to a second line, rather than centering against the taller strip. -->
		<div class="flex shrink-0 items-start gap-2 border-b border-outline-gray-1 px-3 py-2">
			<slot name="toolbar" :doctype="doctype" :meta="meta" :loading="loading" />
		</div>

		<!-- Table chrome region — grows to fill and clips; the list scrolls inside it. -->
		<div class="flex min-h-0 flex-1 flex-col overflow-hidden p-3">
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

		<!-- Footer region: below the list (e.g. the dev wire-output readout). -->
		<div v-if="$slots.footer" class="shrink-0 border-t border-outline-gray-1 px-3 py-2">
			<slot name="footer" :doctype="doctype" :meta="meta" />
		</div>
	</div>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { useDoctypeMeta } from "../../composables/useDoctypeMeta";
import type { RawMetaField } from "../FormLayout/types";

const props = defineProps<{ doctype: string }>();

const { meta, loading, error } = useDoctypeMeta(props.doctype);

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
