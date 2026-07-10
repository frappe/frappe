<template>
	<div class="pfb-image-upload">
		<div v-if="modelValue" class="pfb-image-upload-preview">
			<img :src="modelValue" :alt="alt || ''" />
		</div>
		<div class="pfb-image-upload-actions">
			<button class="es-button" data-size="xs" @click="upload">
				<span v-html="frappe.utils.icon('upload', 'xs')"></span>
				{{ modelValue ? __("Change Image") : __("Upload Image") }}
			</button>
			<button
				v-if="modelValue"
				class="es-button"
				data-size="xs"
				data-theme="red"
				data-variant="ghost"
				@click="$emit('update:modelValue', '')"
			>
				{{ __("Clear") }}
			</button>
		</div>
		<input
			type="text"
			class="pfb-insp-input"
			:placeholder="__('or image URL')"
			:value="modelValue"
			@change="$emit('update:modelValue', $event.target.value.trim())"
		/>
	</div>
</template>

<script setup>
defineProps({
	modelValue: { type: String, default: "" },
	alt: { type: String, default: "" },
});

const emit = defineEmits(["update:modelValue"]);

function upload() {
	new frappe.ui.FileUploader({
		folder: "Home/Attachments",
		restrictions: { allowed_file_types: ["image/*"] },
		on_success: (file_doc) => emit("update:modelValue", file_doc.file_url),
	});
}
</script>
