<script setup>
import { ref, useSlots, provide } from "vue";

let slots = useSlots();

let tab_titles = ref(slots.default().map(tab => tab.props.title));
let selected_tab = ref(tab_titles.value[0]);

provide("selected_tab", selected_tab);
</script>

<template>
	<div class="tabs">
		<div class="tab-header">
			<div v-for="title in tab_titles" :key="title" @click="selected_tab = title">
				{{ title }}
			</div>
		</div>
		<slot />
	</div>
</template>
