<template>
	<button class="btn btn-sm app-button" :class="[isPrimary ? 'btn-primary' : 'btn-default']">
		<slot></slot>
	</button>
</template>

<script setup>
const props = defineProps({
	isPrimary: { type: Boolean, default: false },
});
</script>

<style scoped>
.app-button {
	margin: 5px;
}
</style>
