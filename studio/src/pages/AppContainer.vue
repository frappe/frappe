<template>
	<h2>Hello World</h2>
</template>

<script setup lang="ts">
import { watch, ref } from "vue"
import { useRoute } from "vue-router"

const route = useRoute()
const pageRoute = ref(null)

watch(
	() => route.params.pageRoute,
	() => {
		pageRoute.value = route.params.pageRoute
	},
	{ immediate: true },
)
</script>
