<script setup>
import FieldTypes from "./FieldTypes.vue";
import FieldProperties from "./FieldProperties.vue";
import { ref, watch } from "vue";
import { useStore } from "../store";

let store = useStore();

let tab_titles = [__("Field Types"), __("Field Properties")];
let active_tab = ref(tab_titles[0]);

watch(
	() => store.selected_field,
	value => {
		active_tab.value = value ? tab_titles[1] : tab_titles[0];
	},
	{ deep: true }
);
</script>

<template>
	<div class="tab-header">
		<div
			:class="['tab', active_tab == tab ? 'active' : '']"
			v-for="(tab, i) in tab_titles"
			:key="i"
			@click="active_tab = tab"
		>
			{{ tab }}
		</div>
	</div>
	<div :class="['tab-content', active_tab == tab_titles[0] ? 'active' : '']">
		<FieldTypes />
	</div>
	<div :class="['tab-content', active_tab == tab_titles[1] ? 'active' : '']">
		<FieldProperties />
	</div>
</template>

<style lang="scss" scoped>
.tab-header {
	display: flex;
	justify-content: space-between;
	align-items: center;
	padding: var(--padding-sm);
	background-color: var(--fg-color);
	position: sticky;
	top: 0;
	z-index: 1;

	.tab {
		display: flex;
		justify-content: center;
		align-items: center;
		width: 100%;
		height: 32px;
		border-radius: var(--border-radius-md);
		border: 1px solid var(--dark-border-color);
		cursor: pointer;

		&:not(:first-child) {
			border-left: none;
			border-top-left-radius: 0;
			border-bottom-left-radius: 0;
		}

		&:first-child {
			border-top-right-radius: 0;
			border-bottom-right-radius: 0;
		}

		&.active {
			background-color: var(--bg-gray);
		}
	}
}

.tab-content {
	display: none;
	&.active {
		display: block;
	}
}
</style>
