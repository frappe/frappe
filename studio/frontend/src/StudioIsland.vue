<template>
	<AppRenderer />
</template>

<script setup lang="ts">
import { onUnmounted, provide, watch } from "vue"
import { START_LOCATION, useRouter, type LocationQuery } from "vue-router"
import AppRenderer from "@/AppRenderer.vue"
import { islandPath } from "@/utils/islandRoute"

defineOptions({ inheritAttrs: false })

const props = defineProps<{
	route?: string[]
	query?: LocationQuery
}>()

const emit = defineEmits<{
	title: [title: string]
	route: [route: string[], query: LocationQuery]
}>()

const router = useRouter()

provide("reportTitle", (title: string) => emit("title", title))

watch(
	() => islandPath(props),
	(path) => router.push(path),
)

onUnmounted(
	router.afterEach((to, from, failure) => {
		if (failure || from === START_LOCATION) return
		emit("route", to.path.split("/").filter(Boolean).map(decodeURIComponent), to.query)
	}),
)
</script>
