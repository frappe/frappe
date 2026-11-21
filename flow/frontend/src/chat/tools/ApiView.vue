<template>
	<ResultView :result="result" part="result" />
</template>

<script setup>
import ResultView from "./ResultView.vue";

// call_api wraps what the function returned with its path and title, which the row already shows
defineProps({
	arguments: { type: Object, default: () => ({}) },
	result: { type: Object, default: null },
});
</script>
