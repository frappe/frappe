<template>
	<div class="flex items-center space-x-3 lg:space-x-10 text-xs lg:text-base">
		<div
			class="flex items-center space-x-1 lg:space-x-2 text-ink-gray-5 cursor-pointer"
			:class="{
				'text-ink-gray-9 font-semibold': onUploadStep,
			}"
			@click="emit('updateStep', 'upload', { ...data })"
		>
			<FeatherIcon
				v-if="uploadStepCompleted"
				name="check"
				class="size-5 text-sm border rounded-[5px] p-0.5"
				:class="{
					'text-ink-base bg-surface-gray-10': onUploadStep,
				}"
			/>
			<div
				v-else
				class="text-sm border rounded-[5px] px-1.5 py-0.5"
				:class="{
					'text-ink-base bg-surface-gray-10': onUploadStep,
				}"
			>
				<span> 1 </span>
			</div>
			<div>Upload File</div>
		</div>
		<div
			class="flex items-center space-x-1 lg:space-x-2 text-ink-gray-5"
			:class="{
				'text-ink-gray-9 font-semibold': onMapStep,
				'cursor-pointer': uploadStepCompleted,
			}"
			@click="moveToMapStep()"
		>
			<FeatherIcon
				v-if="mapStepCompleted"
				name="check"
				class="size-5 text-sm border rounded-[5px] p-0.5"
				:class="{
					'text-ink-base bg-surface-gray-10': onMapStep,
				}"
			/>
			<div
				v-else
				class="text-sm border rounded-[5px] px-1.5 py-0.5"
				:class="{
					'text-ink-base bg-surface-gray-10': onMapStep,
				}"
			>
				<span> 2 </span>
			</div>
			<div>Map Data</div>
		</div>
		<div
			class="flex items-center space-x-1 lg:space-x-2 text-ink-gray-5"
			:class="{
				'text-ink-gray-9 font-semibold': onPreviewStep,
				'cursor-pointer': uploadStepCompleted,
			}"
			@click="moveToPreviewStep()"
		>
			<FeatherIcon
				v-if="previewStepCompleted"
				name="check"
				class="size-5 text-sm border rounded-[5px] p-0.5"
				:class="{
					'text-ink-base bg-surface-gray-10': onPreviewStep,
				}"
			/>
			<div
				v-else
				class="text-sm border rounded-[5px] px-1.5 py-0.5"
				:class="{
					'text-ink-base bg-surface-gray-10': onPreviewStep,
				}"
			>
				<span> 3 </span>
			</div>
			<div>Review & Import</div>
		</div>
	</div>
</template>
<script setup lang="ts">
import type { DataImport } from "./types";
import { computed } from "vue";
import { FeatherIcon } from "frappe-ui";

const emit = defineEmits(["updateStep"]);

const props = defineProps<{
	data: DataImport | null;
	step: "list" | "upload" | "map" | "preview";
}>();

const onUploadStep = computed(() => {
	return props.step === "upload";
});

const uploadStepCompleted = computed(() => {
	return props.data?.import_file || props.data?.google_sheets_url;
});

const onMapStep = computed(() => {
	return props.step === "map";
});

const mapStepCompleted = computed(() => {
	return (
		props.data &&
		props.data?.template_options &&
		JSON.parse(props.data.template_options).column_to_field_map
	);
});

const onPreviewStep = computed(() => {
	return props.step === "preview";
});

const previewStepCompleted = computed(() => {
	return props.data?.status === "Success";
});

const moveToMapStep = () => {
	if (uploadStepCompleted.value) {
		emit("updateStep", "map", { ...props.data });
	}
};

const moveToPreviewStep = () => {
	if (uploadStepCompleted.value) {
		emit("updateStep", "preview", { ...props.data });
	}
};
</script>
