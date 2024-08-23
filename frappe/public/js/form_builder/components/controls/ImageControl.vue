<script setup>
const props = defineProps(["df"]);
</script>

<template>
	<div class="control editable">
		<div class="field-controls">
			<slot name="label" />
			<slot name="actions" />
		</div>
		<div class="missing-image" v-html="frappe.utils.icon('restriction', 'md')" />
		<div v-if="df.description" class="mt-2 description" v-html="df.description"></div>
	</div>
</template>
