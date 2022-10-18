<script setup></script>

<template>
	<div class="search-box">
		<input
			class="search-input form-control form-control-sm"
			type="text"
			:placeholder="__('Search fields')"
			@input="event => $emit('update:modelValue', event.target.value)"
		/>
		<span class="search-icon">
			<svg class="icon icon-sm">
				<use href="#icon-search"></use>
			</svg>
		</span>
	</div>
</template>

<style lang="scss" scoped>
.search-box {
	display: flex;
	padding: 0px 9px 9px;
	background-color: var(--fg-color);
	border-bottom: 1px solid var(--border-color);
	position: sticky;
	top: 52px;
	z-index: 1;

	.search-input {
		padding-left: 30px;
	}

	.search-icon {
		position: absolute;
		top: -4px;
		margin-left: 8px;
		display: flex;
		align-items: center;
		height: 100%;
	}
}
</style>
