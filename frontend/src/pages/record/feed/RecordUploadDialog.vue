<!-- The record's one upload dialog, on whichever tab is shown: every upload request opens it. -->
<template>
	<FileUploadDialog
		v-if="dialogMounted"
		v-model:open="dialogOpen"
		multiple
		:attachTo="{ doctype: page.doctype, docname: page.docname }"
		:transport="transport"
		@uploading="onUploading"
	/>
</template>

<script setup lang="ts">
import { inject, ref, watch } from "vue";
import { FileUploadDialog } from "@framework/ui/FileUpload";
import type { RecordPageApi } from "@/recordPage";
import { RecordFeedsKey } from "./recordFeeds";

const props = defineProps<{ page: Pick<RecordPageApi, "doctype" | "docname"> }>();

const feeds = inject(RecordFeedsKey)!;
const transport = feeds.uploadTransport(props.page.doctype, props.page.docname);

// Mounted apart from open: the tray closes the dialog on Upload while the files still go up.
const dialogMounted = ref(false);
const dialogOpen = ref(false);
const busy = ref(false);

watch(dialogOpen, (opened) => {
	if (!opened && !busy.value) dialogMounted.value = false;
});

watch(feeds.uploadRequested, takeUploadRequest, { immediate: true });

function takeUploadRequest(requested: boolean) {
	if (!requested) return;
	feeds.uploadRequested.value = false;
	if (!feeds.docinfo()?.permissions?.write) return;
	dialogMounted.value = true;
	dialogOpen.value = true;
}

function onUploading(uploading: boolean) {
	busy.value = uploading;
	if (!uploading && !dialogOpen.value) dialogMounted.value = false;
}
</script>
