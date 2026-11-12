<!-- A bulk run's result: its records by outcome with one reason each, and the acts on the failed ones. -->
<template>
	<Dialog v-model="open" size="2xl" :title="title">
		<template #default>
			<div class="flex flex-col gap-3">
				<TabButtons v-model="tab" :options="tabs" />
				<div class="-mx-2 flex max-h-80 flex-col overflow-y-auto">
					<ItemListRow
						v-for="record in shown"
						:key="record.name"
						size="md"
						class="shrink-0 !items-start"
					>
						<template #prefix>
							<Icon
								:name="icons[tab]"
								class="mt-0.5 size-4 shrink-0 text-ink-gray-5"
							/>
						</template>
						<template #label>
							<div class="flex min-w-0 flex-1 flex-col gap-1">
								<span class="truncate font-mono text-base text-ink-gray-8">{{
									record.name
								}}</span>
								<span v-if="'error' in record" class="text-sm text-ink-gray-6">
									{{ record.error || __("No reason was given.") }}
								</span>
								<span v-else-if="tab === 'queued'" class="text-sm text-ink-gray-6">
									{{
										__("In the Submission Queue; it settles here when it runs")
									}}
								</span>
							</div>
						</template>
					</ItemListRow>
					<div v-if="!shown.length" class="py-6 text-center text-base text-ink-gray-5">
						{{ __("Nothing here") }}
					</div>
				</div>
			</div>
		</template>
		<template #actions>
			<div class="flex items-center gap-2">
				<a v-if="report.fileUrl" :href="report.fileUrl" target="_blank" rel="noopener">
					<Button :label="__('Open PDF')" icon-left="lucide-file-text" />
				</a>
				<div class="ms-auto flex items-center gap-2">
					<Button
						v-if="failedNames.length && report.select"
						:label="__('Select failed')"
						@click="selectFailed"
					/>
					<Button
						v-if="failedNames.length && report.retry"
						variant="solid"
						:label="__('Retry failed')"
						:loading="retrying"
						@click="retryFailed"
					/>
					<Button
						v-else-if="!failedNames.length"
						variant="solid"
						:label="__('Done')"
						@click="open = false"
					/>
				</div>
			</div>
		</template>
	</Dialog>
</template>

<script setup lang="ts">
import { Button, Dialog, Icon, ItemListRow, TabButtons, toast } from "frappe-ui";
import { computed, onBeforeUnmount, ref, watch } from "vue";
import { __ } from "@/i18n";
import { SETTLE_POLL_MS, bulkPanel, settleQueued, type BulkReport } from "./bulkOutcome";

type Tab = "failed" | "queued" | "done";

const props = defineProps<{ report: BulkReport }>();
const emit = defineEmits<{ close: [] }>();
const open = ref(true);
const retrying = ref(false);
const tab = ref<Tab>(firstTab(props.report));
const icons = { failed: "lucide-circle-x", queued: "lucide-clock", done: "lucide-circle-check" };

const title = computed(() => `${props.report.label} · ${__("{0} records", [props.report.total])}`);
const failedNames = computed(() => props.report.failed.map(({ name }) => name));
const tabs = computed(() => [
	{ value: "failed", label: `${__("Failed")} ${props.report.failed.length}` },
	...(props.report.queued.length
		? [{ value: "queued", label: `${__("Queued")} ${props.report.queued.length}` }]
		: []),
	{ value: "done", label: `${__("Done")} ${props.report.done.length}` },
]);
const shown = computed(() => props.report[tab.value]);

watch(open, (isOpen) => !isOpen && emit("close"));

// A queued submit settles into Done or Failed while the panel is open.
let timer: ReturnType<typeof setTimeout> | undefined;
function pollQueued() {
	timer = setTimeout(async () => {
		const more = await settleQueued(props.report).catch(() => true);
		if (more) pollQueued();
	}, SETTLE_POLL_MS);
}
if (props.report.queued.length) pollQueued();
onBeforeUnmount(() => clearTimeout(timer));

function firstTab({ failed, queued }: BulkReport): Tab {
	return failed.length ? "failed" : queued.length ? "queued" : "done";
}

function selectFailed() {
	props.report.select?.(failedNames.value);
	open.value = false;
}

async function retryFailed() {
	retrying.value = true;
	try {
		await props.report.retry!(failedNames.value);
		if (bulkPanel.value === props.report) open.value = false;
	} catch (error) {
		toast.error(error instanceof Error ? error.message : String(error));
	} finally {
		retrying.value = false;
	}
}
</script>
