<script setup>
import FieldTypes from "./FieldTypes.vue";
import FieldProperties from "./FieldProperties.vue";
import { ref } from "vue";

let tab_titles = [__("Field Types"), __("Field Properties")];
let active_tab = ref(tab_titles[0]);
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
	gap: 10px;
	align-items: center;

	.tab {
		padding: 5px 10px;
		border-radius: 5px;
		cursor: pointer;
		&.active {
			background-color: var(--primary);
			color: white;
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
