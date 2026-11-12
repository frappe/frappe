<!-- The confirmation before a bulk Submit, Cancel or workflow action; queued records and failures stay in the dialog. -->
<template>
	<Dialog v-model="open" :title="title" size="sm" :actions="actions">
		<template #default>
			<p v-if="!result" class="text-base text-ink-gray-6">{{ hint }}</p>
			<template v-else>
				<p class="text-base text-ink-gray-8">{{ summary }}</p>
				<p v-if="result.queued?.length" class="mt-2 text-sm text-ink-gray-6">
					{{ __("Queued: {0}", [result.queued.join(", ")]) }}
				</p>
				<p class="mt-2 whitespace-pre-line text-sm text-ink-red-3">{{ failures }}</p>
			</template>
			<p v-if="failure" class="mt-2 whitespace-pre-line text-sm text-ink-red-3">
				{{ failure }}
			</p>
		</template>
	</Dialog>
</template>

<script setup lang="ts">
import { bulkStatusDocuments, isBulkQueued, type BulkResult } from "@framework/ui/api";
import { Dialog, toast } from "frappe-ui";
import { computed, ref, watch } from "vue";
import { __, __n } from "@/i18n";
import { followBulkRun } from "@/shell/bulkRuns";
import type { BulkStatusAction } from "./bulkStatus";

const props = defineProps<{
	doctype: string;
	action: BulkStatusAction | null;
	finished: () => void;
}>();
const open = defineModel<boolean>({ default: false });

const asked = computed(() => props.action);
const running = ref(false);
const failure = ref("");
const result = ref<BulkResult | null>(null);

// Immediate: the bar mounts this dialog already open, the first time it asks.
watch(
	open,
	() => {
		if (running.value) {
			open.value = true;
			return;
		}
		failure.value = "";
		result.value = null;
	},
	{ immediate: true }
);

const title = computed(() => (asked.value ? `${asked.value.label} ${asked.value.scope}?` : ""));
const hint = computed(() => {
	if (asked.value?.route === "bulk_submit")
		return __("A submitted record can no longer be edited.");
	if (asked.value?.route === "bulk_cancel")
		return __("A cancelled record can no longer be changed.");
	return __("Each record moves through the workflow on its own; one that cannot fails alone.");
});
const summary = computed(() =>
	__("{0} of {1} done, {2} failed", [
		result.value!.done.length,
		result.value!.total,
		result.value!.failed.length,
	])
);
const failures = computed(() =>
	result.value!.failed.map(({ name, error }) => `${name}: ${error}`).join("\n")
);

const actions = computed(() =>
	result.value || failure.value
		? [{ label: __("Close"), onClick: () => (open.value = false) }]
		: [
				{
					label: asked.value?.label ?? "",
					variant: "solid",
					theme: asked.value?.route === "bulk_cancel" ? "red" : undefined,
					loading: running.value,
					onClick: confirm,
				},
		  ]
);

async function confirm() {
	const action = asked.value!;
	running.value = true;
	try {
		const body = action.transition
			? { ...action.body, action: action.transition }
			: action.body;
		const { data } = await bulkStatusDocuments(props.doctype, action.route, body);
		running.value = false;
		if (isBulkQueued(data)) {
			followBulkRun(data.task_id, () => props.finished());
			toast.info(__("{0} is running in the background", [action.label]));
			open.value = false;
			return;
		}
		report(data);
	} catch (error) {
		failure.value = error instanceof Error ? error.message : String(error);
	} finally {
		running.value = false;
	}
}

function report(data: BulkResult) {
	props.finished();
	const queued = data.queued?.length ?? 0;
	if (data.failed.length) {
		result.value = data;
		return;
	}
	if (data.done.length)
		toast.success(
			__n("{0} record done", "{0} records done", data.done.length, [data.done.length])
		);
	if (queued) toast.info(__n("{0} record queued", "{0} records queued", queued, [queued]));
	open.value = false;
}
</script>
