<template>
	<div class="header">
		<div class="app-icon" v-html="appIcon"></div>
		<span class="indicator-pill whitespace-nowrap orange mr-3 py-1">Beta</span>
		<h3 class="title">Editing {{ print_format_name }}</h3>
		<div class="primary-actions">
			<AppButton>Exit</AppButton>
			<AppButton isPrimary>Save</AppButton>
		</div>
	</div>
</template>
<script setup>
import AppButton from "./AppButton.vue";
const props = defineProps({
	print_format_name: String,
	appIcon: String,
});
</script>
<style scoped lang="scss">
.header {
	position: absolute;
	top: 0;
	display: flex;
	justify-content: space-between;
	align-items: center;
	width: 100%;
	height: 60px;
	padding: 0px 10px;
	background: var(--navbar-bg);
	z-index: 1020;
	user-select: none;
}
.app-icon {
	flex: 1;
	max-width: 60px;
}
.title {
	flex: 5;
	margin-bottom: 0;
	user-select: none;
}
.primary-actions {
	min-width: 200px;
	display: flex;
	justify-content: flex-end;
	align-items: center;
}
</style>
