<!-- Used as Button & Heading Control -->
<script setup>
const props = defineProps(["df", "value"]);
</script>

<template>
	<div class="control frappe-control editable" :data-fieldtype="df.fieldtype">
		<!-- label -->
		<div class="field-controls">
			<h4 v-if="df.fieldtype == 'Heading'">
				<slot name="label" />
			</h4>
			<button v-else class="btn btn-xs btn-default">
				<slot name="label" />
			</button>
			<slot name="actions" />
		</div>

		<!-- description -->
		<div v-if="df.description" class="mt-2 description" v-html="df.description" />
	</div>
</template>

<style lang="scss" scoped>
h4 {
	margin-bottom: 0px;
}
</style>
