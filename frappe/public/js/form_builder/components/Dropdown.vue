<template>
	<div class="drop-down">
		<div class="search-box">
			<input
				ref="searchInput"
				class="search-input form-control"
				type="text"
				:placeholder="__('Search field...')"
				@input="(event) => $emit('update:modelValue', event.target.value)"
				:value="modelValue"
				@click.stop
			/>
			<span class="search-icon">
				<div v-html="frappe.utils.icon('search', 'sm')"></div>
			</span>
		</div>
		<div class="drop-down-list">
			<button
				class="btn drop-down-item"
				v-for="(item, i) in items"
				:key="i"
				@click.stop="(i) => item.onClick(i)"
			>
				<slot>{{ item.label }}</slot>
			</button>
		</div>
	</div>
</template>

<script setup>
import { ref, onMounted } from "vue";

const props = defineProps({
	items: {
		type: Array,
		required: true,
	},
	modelValue: {
		type: String,
		default: "",
	},
});

const searchInput = ref(null);

onMounted(() => {
	searchInput.value.focus();
});
</script>

<style lang="scss" scoped>
.drop-down {
	display: inline-block;
	background-color: var(--fg-color);
	box-shadow: var(--shadow-base) !important;
	border-radius: var(--border-radius-sm);
	top: 30px;
	right: 0;
	width: 170px;
	z-index: 99999999;
}

.drop-down-list {
	overflow-y: auto;
	max-height: 250px;
	text-align: left;
	padding: 0 6px 6px;
}

.drop-down-item {
	font-size: small;
	text-align: left;
	border-radius: var(--border-radius-sm);
	margin: 1px 0px;
	width: 100%;

	&:hover {
		background-color: var(--bg-light-gray);
	}
}

.search-box {
	padding: 6px;
	.search-input {
		padding-left: 30px;
		font-size: small;
		width: 100% !important;
		background-color: var(--control-bg) !important;
	}

	.search-icon {
		position: absolute;
		left: 13px;
		top: 11px;
	}
}
</style>
