<script setup>
import AttachmentChip from "./AttachmentChip.vue";

defineProps({
	content: { type: String, default: "" },
	attachments: { type: Array, default: () => [] },
});
</script>

<template>
	<div class="flex flex-col items-end gap-1.5">
		<div v-if="attachments.length" class="flex max-w-[88%] flex-wrap justify-end gap-1.5">
			<AttachmentChip
				v-for="(a, i) in attachments"
				:key="`${a.file_name}-${i}`"
				:file-name="a.file_name"
				:file-size="a.file_size"
			/>
		</div>
		<div
			class="max-w-[88%] whitespace-pre-wrap break-words rounded-2xl bg-surface-gray-2 px-3.5 py-2.5 text-[length:var(--text-base)] font-normal leading-relaxed text-ink-gray-9"
		>
			{{ content }}
		</div>
	</div>
</template>
