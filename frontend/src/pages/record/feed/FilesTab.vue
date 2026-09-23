<!-- The Files tab: the record's attachments and a script's rows, oldest first, with an
     upload button and a delete control per file for a reader who may write. -->
<template>
	<RecordFeed>
		<div class="flex items-center justify-between gap-3">
			<span class="text-base font-medium text-ink-gray-8">{{ countLabel }}</span>
			<Button
				v-if="canWrite"
				iconLeft="lucide-upload"
				:label="__('Upload')"
				data-file-upload
				@click="open"
			/>
		</div>

		<div v-if="rows.length" class="flex flex-col">
			<template v-for="row in rows" :key="row.name">
				<component
					:is="row.component"
					v-if="isScriptRow(row)"
					v-bind="{ ...row.props, page }"
				/>
				<div
					v-else
					class="flex items-center gap-3 rounded-6 px-2 py-2 hover:bg-surface-gray-1"
					:data-file-row="row.name"
				>
					<span
						class="grid size-8 shrink-0 place-items-center rounded-4 bg-surface-gray-2 text-ink-gray-5"
					>
						<span
							class="size-4"
							:class="isImage(row) ? 'lucide-image' : 'lucide-file-text'"
							aria-hidden="true"
						/>
					</span>
					<div class="min-w-0 flex-1">
						<a
							:href="row.file_url"
							target="_blank"
							rel="noopener"
							class="block truncate text-base font-medium text-ink-gray-8 hover:underline"
						>
							{{ row.file_name }}
						</a>
						<div class="flex items-center gap-1 text-sm text-ink-gray-5">
							<span class="truncate">{{ personOf(docinfo, row.owner).name }}</span>
							<span aria-hidden="true">·</span>
							<TimeAgo :timestamp="row.creation" class="text-sm" />
						</div>
					</div>
					<span
						v-if="row.is_private"
						class="lucide-lock size-3.5 shrink-0 text-ink-gray-4"
						role="img"
						:aria-label="__('Private')"
					/>
					<Button
						v-if="canWrite"
						variant="ghost"
						icon="lucide-trash-2"
						:tooltip="__('Delete')"
						:aria-label="__('Delete')"
						data-file-remove
						@click="remove(row)"
					/>
				</div>
			</template>
		</div>
		<div v-else class="flex flex-col items-center justify-center gap-3 py-8">
			<span class="lucide-paperclip size-7 text-ink-gray-4" aria-hidden="true" />
			<span class="text-lg font-medium text-ink-gray-8">{{ __("No files yet") }}</span>
		</div>

		<FileUploadDialog
			v-if="dialogMounted"
			v-model:open="dialogOpen"
			multiple
			:attachTo="{ doctype: page.doctype, docname: page.docname }"
			:transport="transport"
			@uploading="onUploading"
		/>
	</RecordFeed>
</template>

<script setup lang="ts">
import { computed, inject, ref, watch } from "vue";
import { Button, toast } from "frappe-ui";
import { FileUploadDialog } from "@framework/ui/FileUpload";
import TimeAgo from "@framework/ui/components/ActivityTimeline/TimeAgo.vue";
import { errorMessage, type FileRow, type RecordPageApi } from "@/recordPage";
import { __, __n } from "@/i18n";
import { personOf } from "../panel/context";
import { filesInTimeOrder, isImage, isScriptRow } from "./files";
import RecordFeed from "./RecordFeed.vue";
import { RecordFeedsKey } from "./recordFeeds";

const props = defineProps<{ page: RecordPageApi }>();

const feeds = inject(RecordFeedsKey)!;
const transport = feeds.uploadTransport(props.page.doctype, props.page.docname);

const docinfo = computed(() => feeds.docinfo());
const canWrite = computed(() => Boolean(docinfo.value?.permissions?.write));
const rows = computed(() =>
	filesInTimeOrder(feeds.fileRows(), feeds.controller()?.files.visible() ?? [])
);
const countLabel = computed(() => {
	const count = feeds.fileRows().length;
	return __n("{0} file", "{0} files", count, [count]);
});

// Mounted apart from open: the tray closes the dialog on Upload while the files still go up.
const dialogMounted = ref(false);
const dialogOpen = ref(false);
const busy = ref(false);

watch(dialogOpen, (opened) => {
	if (!opened && !busy.value) dialogMounted.value = false;
});

function open() {
	dialogMounted.value = true;
	dialogOpen.value = true;
}

function onUploading(uploading: boolean) {
	busy.value = uploading;
	if (!uploading && !dialogOpen.value) dialogMounted.value = false;
}

async function remove(row: FileRow) {
	const confirmed = await props.page.dialog.confirm({
		title: __("Delete file?"),
		message: __("{0} will be deleted from this record.", [row.file_name]),
		confirmLabel: __("Delete"),
		cancelLabel: __("Cancel"),
	});
	if (!confirmed) return;
	try {
		await feeds.removeFile(props.page.doctype, props.page.docname, row.name);
	} catch (error) {
		toast.error(errorMessage(error));
	}
}
</script>
