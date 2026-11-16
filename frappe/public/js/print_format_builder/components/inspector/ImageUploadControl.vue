<template>
	<div class="pfb-image-upload">
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
</template>

<script setup>
defineProps({
	modelValue: { type: String, default: "" },
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
