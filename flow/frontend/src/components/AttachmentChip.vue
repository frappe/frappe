<script setup>
import { computed } from "vue";
import { FeatherIcon, Spinner } from "@/lib/ui";
import { __ } from "@/lib/translate";

const props = defineProps({
	fileName: { type: String, default: "" },
	fileSize: { type: Number, default: 0 },
	status: { type: String, default: "ready" }, // uploading | ready | error
	error: { type: String, default: "" },
	removable: { type: Boolean, default: false },
});
defineEmits(["remove"]);

const sizeLabel = computed(() => {
	const b = props.fileSize || 0;
	if (b < 1024) return `${b} B`;
	if (b < 1024 * 1024) return `${Math.round(b / 1024)} KB`;
	return `${(b / (1024 * 1024)).toFixed(1)} MB`;
});

const title = computed(() =>
	props.status === "error" ? props.error || __("Couldn't attach file") : props.fileName
);
</script>

<template>
	<div
		class="flex max-w-[200px] items-center gap-1.5 rounded-lg border bg-surface-gray-1 py-1 pl-2 pr-1.5"
		:class="status === 'error' ? 'border-outline-gray-4' : 'border-outline-gray-2'"
		:title="title"
	>
		<FeatherIcon name="file-text" class="h-3.5 w-3.5 shrink-0 text-ink-gray-5" />
		<div class="min-w-0 flex-1">
			<div class="truncate text-[12px] font-medium leading-tight text-ink-gray-8">
				{{ fileName }}
			</div>
			<div class="text-[10.5px] leading-tight text-ink-gray-5">
				<span v-if="status === 'error'" class="font-medium text-ink-gray-7">{{
					__("Failed")
				}}</span>
				<span v-else-if="status === 'uploading'">{{ __("Uploading…") }}</span>
				<span v-else>{{ sizeLabel }}</span>
			</div>
		</div>
		<Spinner v-if="status === 'uploading'" class="h-3.5 w-3.5 shrink-0 text-ink-gray-5" />
		<button
			v-else-if="removable"
			class="flex h-4 w-4 shrink-0 items-center justify-center rounded text-ink-gray-5 hover:bg-surface-gray-3 hover:text-ink-gray-7"
			:title="__('Remove')"
			@click="$emit('remove')"
		>
			<FeatherIcon name="x" class="h-3 w-3" />
		</button>
	</div>
</template>
