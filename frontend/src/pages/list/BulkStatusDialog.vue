<!-- The confirmation before a bulk Submit, Cancel or workflow action; the outcome goes to the bulk tray and result panel. -->
<template>
	<Dialog v-model="open" :title="title" size="sm" :actions="actions">
		<template #default>
			<p class="text-base text-ink-gray-6">{{ hint }}</p>
			<p v-if="failure" class="mt-2 whitespace-pre-line text-sm text-ink-red-3">
				{{ failure }}
			</p>
		</template>
	</Dialog>
</template>

<script setup lang="ts">
import { bulkStatusDocuments } from "@framework/ui/api";
import { Dialog } from "frappe-ui";
import { computed, ref, watch } from "vue";
import { __ } from "@/i18n";
import { runBulk } from "@/shell/bulkOutcome";
import type { BulkStatusAction } from "./bulkStatus";

const props = defineProps<{
	doctype: string;
	action: BulkStatusAction | null;
	finished: () => void;
	select: (names: string[]) => void;
}>();
const open = defineModel<boolean>({ default: false });

const asked = computed(() => props.action);
const running = ref(false);
const failure = ref("");

// Immediate: the bar mounts this dialog already open, the first time it asks.
watch(
	open,
	() => {
		if (running.value) {
			open.value = true;
			return;
		}
		failure.value = "";
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
const actions = computed(() =>
	failure.value
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

// The outcome (a toast, the result panel, or the tray) is the shell's; the dialog only shows a request that failed.
async function confirm() {
	const action = asked.value!;
	running.value = true;
	try {
		await runBulk({
			label: action.label,
			doctype: props.doctype,
			send: (names) => {
				const body = names ? { names } : action.body;
				return bulkStatusDocuments(props.doctype, action.route, action.transition ? { ...body, action: action.transition } : body);
			},
			select: props.select,
			finished: props.finished,
		});
		open.value = false;
	} catch (error) {
		failure.value = error instanceof Error ? error.message : String(error);
	} finally {
		running.value = false;
	}
}
</script>
