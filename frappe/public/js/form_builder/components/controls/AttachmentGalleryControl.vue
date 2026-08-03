<script setup>
const props = defineProps(["df"]);

const attachments = ["example-image.png", "document.pdf"];
</script>

<template>
	<div class="control editable frappe-control">
		<div class="field-controls">
			<slot name="label" />
			<slot name="actions" />
		</div>

		<div class="attachment-gallery">
			<div
				v-for="attachment in attachments"
				:key="attachment"
				class="attachment-gallery-item-wrapper"
			>
				<div class="attachment-gallery-item attachment-gallery-file">
					<div class="attachment-gallery-placeholder">
						<div v-html="frappe.utils.icon('file', 'lg')" />
						<span class="attachment-gallery-filename">{{ attachment }}</span>
					</div>
				</div>
			</div>
			<div
				class="attachment-gallery-item attachment-gallery-upload"
				v-html="frappe.utils.icon('upload', 'lg')"
			/>
		</div>

		<div v-if="df.description" class="mt-2 description" v-html="__(df.description)" />
	</div>
</template>
