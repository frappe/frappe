<script setup>
import { inject } from "vue";

let props = defineProps({
	title: {
		type: String,
		required: true
	}
});

let selected_tab = inject("selected_tab");
</script>

<template>
	<div v-show="selected_tab == title">
		<slot />
	</div>
</template>
