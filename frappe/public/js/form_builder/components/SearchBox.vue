<script setup></script>

<template>
	<div class="search-box">
		<input
			class="search-input form-control"
			type="text"
			:placeholder="__('Search fields')"
			@input="event => $emit('update:modelValue', event.target.value)"
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
	padding: 0px 9px 9px;
	background-color: var(--fg-color);
	border-bottom: 1px solid var(--border-color);

	.search-input {
		padding-left: 30px;
	}

	.search-icon {
		position: absolute;
		left: 16px;
		top: 5px;
	}
}
</style>
