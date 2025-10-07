<!-- Used as EmbedPdf Control -->
<script setup>
const props = defineProps(["df"]);
</script>

<template>
	<div class="control editable">
		<!-- label -->
		<div class="field-controls">
			<slot name="label" />
			<slot name="actions" />
		</div>

		<!-- embed pdf button -->
		<button class="btn btn-sm btn-default">{{ __("Upload PDF") }}</button>

		<!-- pdf preview placeholder -->
		<div
			class="pdf-preview-placeholder mt-2"
			style="border: 1px dashed #ddd; padding: 20px; text-align: center; border-radius: 4px"
		>
			<i
				class="fa fa-file-pdf-o"
				style="font-size: 24px; color: #dc3545; margin-bottom: 5px"
			></i>
			<div style="color: #6c757d; font-size: 12px">{{ __("PDF Preview") }}</div>
		</div>

		<!-- description -->
		<div v-if="df.description" class="mt-2 description" v-html="df.description"></div>
	</div>
</template>
