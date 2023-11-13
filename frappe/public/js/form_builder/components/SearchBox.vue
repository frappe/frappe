<script setup></script>

<template>
	<div class="search-box">
		<input
			class="search-input form-control"
			type="text"
			:placeholder="__('Search properties...')"
			@input="(event) => $emit('update:modelValue', event.target.value)"
		/>
		<span class="search-icon">
			<div v-html="frappe.utils.icon('search', 'sm')"></div>
		</span>
	</div>
</template>

<style lang="scss" scoped>
.search-box {
	display: flex;
	position: relative;
	background-color: var(--fg-color);
	width: 100%;

	.search-input {
		padding-left: 30px;
	}

	.search-icon {
		position: absolute;
		left: 7px;
		top: 2px;
	}
}
</style>
