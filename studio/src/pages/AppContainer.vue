<template>
	<AppComponent v-if="rootBlock" :block="rootBlock" />
</template>

<script setup lang="ts">
import { watch, ref } from "vue"
import { useRoute } from "vue-router"
import { usePageMeta } from "frappe-ui"

import { getBlockInstance, jsonToJs, findPageWithRoute } from "@/utils/helpers"
import AppComponent from "@/components/AppComponent.vue"

import useAppStore from "@/stores/appStore"

const store = useAppStore()
const route = useRoute()
const page = ref(null)
const rootBlock = ref(null)

watch(
	() => route.path,
	async () => {
		let { appRoute, pageRoute } = route.params
		const isDynamic = route.meta?.isDynamic
		if (appRoute === "studio") return

		let currentPath = ""
		if (isDynamic) {
			currentPath = route.matched?.[0]?.path
		} else if (pageRoute) {
			currentPath = pageRoute[0]
		}

		if (currentPath) {
			page.value = await findPageWithRoute(appRoute, currentPath)
			if (!page.value) return
			const blocks = jsonToJs(page.value?.blocks)
			if (blocks) {
				rootBlock.value = getBlockInstance(blocks[0])
			}
			await store.setLocalState({ route: route })
			await store.setPageResources(page.value)
		} else {
			rootBlock.value = null
		}
	},
	{ immediate: true },
)

usePageMeta(() => {
	return {
		title: page.value?.page_title,
	}
})
</script>
