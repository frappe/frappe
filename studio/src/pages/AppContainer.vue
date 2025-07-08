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

import type { StudioPage } from "@/types/Studio/StudioPage"
import Block from "@/utils/block"

const store = useAppStore()
const route = useRoute()
const page = ref<StudioPage | null>(null)

const rootBlock = ref<Block | null>(null)

watch(
	() => route.path,
	async () => {
		let { pageRoute } = route.params as { pageRoute: string[] }
		const isDynamic = route.meta?.isDynamic

		let currentPath = "/"
		if (isDynamic) {
			currentPath = route.matched?.[0]?.path
		} else if (pageRoute) {
			currentPath = pageRoute[0]
		}

		if (currentPath) {
			page.value = await findPageWithRoute(window.app_name, currentPath)
			if (!page.value) return
			await store.setLocalState({ route: route })
			await store.setPageData(page.value)
			await store.setPageWatchers(page.value)

			const blocks = window.is_preview
				? jsonToJs(page.value?.draft_blocks || page.value?.blocks)
				: jsonToJs(page.value?.blocks)
			if (blocks) {
				rootBlock.value = getBlockInstance(blocks[0])
			}
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
