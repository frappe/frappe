<!-- The corner tray of background bulk runs, mounted by the shell once a run exists, and the result panel it opens. -->
<template>
	<div
		v-if="runs.length"
		class="fixed bottom-24 right-[calc(1rem+var(--shell-nav-inset-right,0px))] z-20 flex w-80 flex-col overflow-hidden rounded-5 bg-surface-base shadow-2xl"
	>
		<div
			class="flex h-10 items-center justify-between border-b border-outline-gray-1 ps-3 pe-1"
		>
			<span class="text-base font-medium text-ink-gray-9">{{ __("Bulk actions") }}</span>
			<Button
				variant="ghost"
				:icon="collapsed ? 'lucide-chevron-up' : 'lucide-chevron-down'"
				:label="collapsed ? __('Expand') : __('Collapse')"
				@click="collapsed = !collapsed"
			/>
		</div>
		<div
			v-if="!collapsed"
			class="flex max-h-72 flex-col divide-y divide-outline-gray-1 overflow-y-auto"
		>
			<div v-for="run in runs" :key="run.taskId" class="flex flex-col gap-1.5 px-3 py-2.5">
				<div class="flex items-center gap-2 text-base">
					<span class="truncate text-ink-gray-9">{{ labelOf(run) }}</span>
					<div class="ms-auto flex shrink-0 items-center gap-1">
						<Button
							v-if="hasDetails(run)"
							size="sm"
							variant="ghost"
							:label="__('View')"
							@click="view(run)"
						/>
						<Button
							v-if="!live(run)"
							size="sm"
							variant="ghost"
							icon="lucide-x"
							:label="__('Dismiss')"
							@click="dismiss(run)"
						/>
					</div>
				</div>
				<Progress v-if="live(run)" :value="run.progress" size="sm" />
				<span v-if="live(run)" class="truncate text-sm text-ink-gray-5">{{
					run.stage || __(run.status)
				}}</span>
				<span v-else class="truncate text-sm text-ink-gray-6">{{ outcome(run) }}</span>
			</div>
		</div>
	</div>
	<BulkResultPanel
		v-if="bulkPanel"
		:key="bulkPanel.label"
		:report="bulkPanel"
		@close="bulkPanel = null"
	/>
</template>

<script setup lang="ts">
import { Button, Progress } from "frappe-ui";
import { defineAsyncComponent, ref, watchEffect } from "vue";
import { __ } from "@/i18n";
import { bulkPanel, bulkRunMeta, reportOfRun } from "./bulkOutcome";
import { dismissBulkRun, useBulkRuns, type BulkRun } from "./bulkRuns";

const CLEAN_DISMISS_MS = 6000;

const BulkResultPanel = defineAsyncComponent(() => import("./BulkResultPanel.vue"));
const runs = useBulkRuns();
const collapsed = ref(false);
const timers = new Set<string>();

// A run that passed in full leaves by itself; one with failures, queued records or a file stays until dismissed.
watchEffect(() => {
	for (const run of runs.value) {
		if (live(run) || !run.result || hasDetails(run) || timers.has(run.taskId)) continue;
		timers.add(run.taskId);
		setTimeout(() => dismiss(run), CLEAN_DISMISS_MS);
	}
});

function live(run: BulkRun) {
	return run.status === "Queued" || run.status === "Running";
}

function hasDetails(run: BulkRun) {
	const { result } = run;
	return Boolean(result && (result.failed.length || result.queued?.length || result.file_url));
}

function labelOf(run: BulkRun) {
	return bulkRunMeta.get(run.taskId)?.label || run.taskName || __("Bulk action");
}

function outcome(run: BulkRun) {
	const { result } = run;
	if (!result) return run.error || __(run.status);
	const parts = [__("{0} done", [result.done.length]), __("{0} failed", [result.failed.length])];
	if (result.queued?.length) parts.push(__("{0} queued", [result.queued.length]));
	return parts.join(", ");
}

function view(run: BulkRun) {
	if (run.result) bulkPanel.value = reportOfRun(run.taskId, labelOf(run), run.result);
}

function dismiss(run: BulkRun) {
	timers.delete(run.taskId);
	bulkRunMeta.delete(run.taskId);
	dismissBulkRun(run.taskId);
}
</script>
