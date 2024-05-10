<script setup>
const props = defineProps(["df"]);
</script>

<template>
	<div class="control editable">
		<div class="field-controls">
			<slot name="label" />
			<slot name="actions" />
		</div>
		<div class="signature-field"></div>
		<div v-if="df.description" class="mt-2 description" v-html="df.description"></div>
	</div>
</template>

<style lang="scss" scoped>
.signature-field {
	border-radius: var(--border-radius);
	height: 200px;
	display: flex;
	justify-content: center;

	&::before {
		content: "";
		background-color: var(--text-on-gray);
		width: 70%;
		height: 2px;
		margin-top: 150px;
	}
}
</style>
