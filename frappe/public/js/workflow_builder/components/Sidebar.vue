<script setup>
import Properties from "./Properties.vue";
</script>

<template>
	<div class="sidebar-container">
		<Properties />
	</div>
</template>

<style lang="scss" scoped>
.sidebar-container {
	position: relative;
	width: 300px;
	height: 100%;
	margin-right: 10px;
	border-radius: var(--border-radius-lg);
	border: 1px solid var(--border-color);
	background-color: var(--fg-color);
}
</style>
