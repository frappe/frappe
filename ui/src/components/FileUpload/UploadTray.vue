<template>
	<div
		v-if="batches.length"
		class="fixed z-50 w-80 overflow-hidden rounded-lg border border-outline-gray-2 bg-surface-base shadow-lg"
		:class="positionClass"
		@mouseenter="onEnter"
	>
		<!-- Header: aggregate state + collapse/close -->
		<div class="flex items-center gap-2 border-b border-outline-gray-1 px-3 py-2">
			<span
				v-if="isUploading"
				class="lucide-loader-2 size-4 animate-spin text-ink-gray-6"
				aria-hidden="true"
			/>
			<span
				v-else-if="allDone"
				class="lucide-check-circle-2 size-4 text-ink-green-6"
				aria-hidden="true"
			/>
			<span
				v-else-if="hasError"
				class="lucide-alert-circle size-4 text-ink-red-8"
				aria-hidden="true"
			/>
			<span class="flex-1 truncate text-p-sm-medium text-ink-gray-8">
				{{ headerLabel }}
			</span>
			<button
				type="button"
				aria-label="Toggle"
				class="grid size-5 place-items-center rounded text-ink-gray-5 hover:bg-surface-gray-2"
				@click="expanded = !expanded"
			>
				<span
					:class="expanded ? 'lucide-chevron-down' : 'lucide-chevron-up'"
					class="size-4"
				/>
			</button>
			<button
				type="button"
				aria-label="Close"
				class="grid size-5 place-items-center rounded text-ink-gray-5 hover:bg-surface-gray-2"
				@click="dismiss"
			>
				<span class="lucide-x size-4" />
			</button>
		</div>

		<!-- Body: one block per batch -->
		<div v-if="expanded" class="max-h-72 overflow-y-auto">
			<div v-for="batch in batches" :key="batch.id" class="px-3 py-2">
				<div class="mb-1 truncate text-p-xs text-ink-gray-5">{{ batch.label }}</div>
				<div
					v-for="item in batch.items"
					:key="item.id"
					class="flex items-center gap-2 py-1"
				>
					<span class="min-w-0 flex-1 truncate text-p-sm text-ink-gray-8">
						{{ item.name }}
					</span>
					<span
						v-if="item.status === 'done'"
						class="lucide-check size-3.5 shrink-0 text-ink-green-6"
						aria-hidden="true"
					/>
					<span v-else-if="item.status === 'error'" class="text-p-xs text-ink-red-8">
						Failed
					</span>
					<span v-else class="shrink-0 text-p-xs text-ink-gray-5">
						{{ Math.round(item.progress * 100) }}%
					</span>
					<button
						v-if="item.status === 'uploading' && batch.cancel"
						type="button"
						aria-label="Cancel"
						class="grid size-4 place-items-center rounded text-ink-gray-5 hover:bg-surface-gray-2"
						@click="batch.cancel(item.id)"
					>
						<span class="lucide-x size-3" />
					</button>
					<button
						v-if="item.status === 'error' && batch.retry"
						type="button"
						aria-label="Retry"
						class="grid size-4 place-items-center rounded text-ink-gray-5 hover:bg-surface-gray-2"
						@click="batch.retry(item.id)"
					>
						<span class="lucide-rotate-cw size-3" />
					</button>
				</div>
			</div>
		</div>

		<!-- Collapsed: a thin aggregate bar while uploading. Once everything is
		     done the bar is dropped — a full-width fill is meaningless and the
		     dark stripe looked like a black band under the header. -->
		<div v-else-if="!allDone" class="h-1 w-full bg-surface-gray-2">
			<div
				class="h-full bg-surface-gray-8 transition-all"
				:style="{ width: `${Math.round(aggregateProgress * 100)}%` }"
			/>
		</div>
	</div>
</template>

<script setup lang="ts">
// App-root singleton: a minimized, Gmail/Drive-style floating progress card
// (bottom-right by default; `side` picks the bottom corner) that observes the
// module-level `uploadTray` store. Because the store outlives any one dialog,
// in-flight uploads keep reporting here after the dialog that started them
// closes. Expand for per-file cancel/retry; collapse to a single aggregate bar;
// auto-dismisses finished batches shortly after they all complete. Mount this
// ONCE near the app root.
import { computed, onUnmounted, ref, watch } from "vue";
import { clearAllBatches, clearFinishedBatches, useTray } from "./uploadTray";

// The tray always sits at the bottom; `side` picks which bottom corner.
// Default reproduces the original bottom-right placement.
const props = withDefaults(
	defineProps<{
		side?: "left" | "right";
	}>(),
	{ side: "right" }
);

const { batches, isUploading, allDone } = useTray();

const expanded = ref(true);

const positionClass = computed(() => ["bottom-4", props.side === "left" ? "left-4" : "right-4"]);

const aggregateProgress = computed(() => {
	const items = batches.value.flatMap((batch) => batch.items);
	if (!items.length) return 0;
	const sum = items.reduce(
		(total, item) => total + (item.status === "done" ? 1 : item.progress),
		0
	);
	return sum / items.length;
});

// How many items finished in `error`. Drives the "some uploads failed" header
// state: a batch can settle with no item uploading yet not all-done, in which
// case neither the spinner nor the done-check fits.
const failedCount = computed(
	() =>
		batches.value.flatMap((batch) => batch.items).filter((item) => item.status === "error")
			.length
);
const hasError = computed(() => failedCount.value > 0);

const headerLabel = computed(() => {
	const items = batches.value.flatMap((batch) => batch.items);
	const done = items.filter((item) => item.status === "done").length;
	if (allDone.value) return `Uploaded ${done} file${done === 1 ? "" : "s"}`;
	// Settled with failures and nothing uploading: report the split.
	if (!isUploading.value && hasError.value)
		return `${done} uploaded, ${failedCount.value} failed`;
	return `Uploading ${done}/${items.length}`;
});

// The ✕ is an explicit close: drop every batch, even ones that settled with a
// failure. (Auto-dismiss, below, still only sweeps fully-done batches.)
function dismiss() {
	clearAllBatches();
}

// Auto-dismiss finished batches a few seconds after they complete — UNLESS the
// user has hovered the tray. The first hover counts as engagement: it cancels
// auto-dismiss for good (no restart on leave), so the card stays put until they
// close it manually with the X. `engaged` resets when the tray empties, so the
// next upload cycle gets a fresh auto-dismiss. setTimeout (not a real clock read)
// is fine here — it only schedules cleanup of completed batches.
let dismissTimer: ReturnType<typeof setTimeout> | null = null;
let engaged = false;

function scheduleDismiss() {
	if (dismissTimer) clearTimeout(dismissTimer);
	dismissTimer = null;
	if (engaged) return;
	dismissTimer = setTimeout(() => clearFinishedBatches(), 4000);
}

function onEnter() {
	engaged = true;
	if (dismissTimer) clearTimeout(dismissTimer);
	dismissTimer = null;
}

watch(allDone, (done) => {
	if (done) scheduleDismiss();
});

// A fresh cycle (tray emptied, then a new batch) should auto-dismiss again.
watch(
	() => batches.value.length,
	(length) => {
		if (length === 0) engaged = false;
	}
);

onUnmounted(() => {
	if (dismissTimer) clearTimeout(dismissTimer);
});
</script>
