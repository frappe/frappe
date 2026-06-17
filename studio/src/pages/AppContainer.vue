<template>
	<AppComponent v-if="rootBlock" :block="rootBlock" />
</template>

<script setup lang="ts">
import { watch, ref } from "vue"
import { useRoute } from "vue-router"
import { usePageMeta } from "frappe-ui"

import { findPageWithRoute } from "@/utils/helpers"
import { getBlockInstance } from "@/utils/serializer"
import AppComponent from "@/components/AppComponent.vue"

import useAppStore from "@/stores/appStore"
import useCodeStore from "@/stores/codeStore"

import type { StudioPage } from "@/types/Studio/StudioPage"
import Block from "@/utils/block"

const store = useAppStore()
const route = useRoute()
const codeStore = useCodeStore()
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
			await store.setPageData(page.value)
			await codeStore.setPageScript(page.value, Boolean(page.value.is_standard))

			const blocks = window.is_preview
				? JSON.parse(page.value?.draft_blocks || page.value?.blocks)
				: JSON.parse(page.value?.blocks)
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
