<template>
	<div
		class="flex min-h-64 flex-col items-center justify-center gap-3 rounded-lg border border-dashed p-6 text-center text-ink-gray-5 transition-colors"
		:class="isDragging ? 'border-outline-gray-3 bg-surface-gray-2' : 'border-outline-gray-2'"
		@dragover.prevent="isDragging = true"
		@dragleave.prevent="isDragging = false"
		@drop.prevent="onDrop"
	>
		<input
			ref="input"
			type="file"
			class="hidden"
			:multiple="multiple"
			:accept="accept"
			@change="onInput"
		/>
		<span class="lucide-upload-cloud size-8 text-ink-gray-4" aria-hidden="true" />
		<div v-if="!isDragging" class="text-p-sm">
			Drag &amp; drop {{ multiple ? "files" : "a file" }} here, or
			<button
				type="button"
				class="font-medium text-ink-gray-8 underline underline-offset-2 hover:text-ink-gray-9"
				@click="browse"
			>
				browse
			</button>
		</div>
		<div v-else class="text-p-sm">Drop to add</div>
	</div>
</template>

<script setup lang="ts">
// Device source: drag-and-drop (files and folders) plus a Browse button. It is
// "dumb" — it only surfaces the chosen `File[]` via `files`; the dialog decides
// what to do with them (validate + enqueue through the uploader). `accept`
// mirrors the native input filter; folder drops are walked recursively.
import { ref } from "vue";

defineProps<{ accept?: string; multiple?: boolean }>();
const emit = defineEmits<{ files: [File[]] }>();

const input = ref<HTMLInputElement | null>(null);
const isDragging = ref(false);

function browse() {
	input.value?.click();
}

function onInput() {
	const el = input.value;
	if (!el?.files) return;
	emit("files", Array.from(el.files));
	el.value = "";
}

async function onDrop(event: DragEvent) {
	isDragging.value = false;
	const data = event.dataTransfer;
	if (!data) return;

	// Prefer the entries API so dropped folders expand into their files; fall
	// back to the flat FileList when entries aren't available.
	const entries = Array.from(data.items)
		.map((item) => item.webkitGetAsEntry?.())
		.filter(Boolean) as any[];

	if (entries.length) {
		const files: File[] = [];
		for (const entry of entries) await walkEntry(entry, files);
		if (files.length) emit("files", files);
		return;
	}
	if (data.files.length) emit("files", Array.from(data.files));
}

/** Depth-first walk of a dropped FileSystemEntry tree, collecting files. */
async function walkEntry(entry: any, out: File[]): Promise<void> {
	if (entry.isFile) {
		const file = await new Promise<File>((resolve, reject) => entry.file(resolve, reject));
		out.push(file);
		return;
	}
	if (entry.isDirectory) {
		// readEntries yields entries in batches (Chrome caps at 100 per call), so
		// keep reading until a call returns an empty array to avoid dropping files.
		const reader = entry.createReader();
		while (true) {
			const children: any[] = await new Promise((resolve) =>
				reader.readEntries(resolve, () => resolve([]))
			);
			if (!children.length) break;
			for (const child of children) await walkEntry(child, out);
		}
	}
}
</script>
