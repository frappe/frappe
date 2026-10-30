<template>
	<div v-if="inline" class="pfb-image-upload-inline">
		<input
			type="text"
			class="form-control form-control-sm pfb-insp-input"
			:placeholder="__('Image URL')"
			:value="modelValue"
			@change="$emit('update:modelValue', $event.target.value.trim())"
		/>
		<button
			class="es-button"
			data-size="xs"
			data-variant="ghost"
			:title="__('Upload Image')"
			@click="upload"
			v-html="frappe.utils.icon('upload', 'xs')"
		></button>
	</div>
	<div v-else class="pfb-image-upload">
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
			class="form-control form-control-sm pfb-insp-input"
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
	inline: { type: Boolean, default: false },
});

const emit = defineEmits(["update:modelValue"]);

function upload() {
	new frappe.ui.FileUploader({
		folder: "Home/Attachments",
		restrictions: { allowed_file_types: ["image/*"] },
		make_attachments_public: true,
		on_success: (file_doc) => emit("update:modelValue", file_doc.file_url),
	});
}
</script>
