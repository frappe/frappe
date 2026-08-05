<template>
	<AppComponent v-if="rootBlock" :block="rootBlock" />
</template>

<script setup lang="ts">
import { watch, ref } from "vue"
import { useRoute } from "vue-router"
import { usePageMeta } from "frappe-ui"

import { findPageWithRoute } from "@/utils/helpers"
import { getBlockInstance } from "@/utils/serializer"
import { useLivePreview } from "@/utils/useLivePreview"
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
let loadedPath: string | null = null

async function handleRouteChange() {
	const currentPath = resolveCurrentPath()
	if (currentPath && currentPath === loadedPath && page.value) {
		// param-only navigation (/articles/a -> /articles/b): everything stays mounted —
		// resources with route-dependent inputs re-evaluate and reload themselves (codeStore live bindings)
		return
	}
	await loadPage()
}

async function loadPage() {
	const currentPath = resolveCurrentPath()
	if (!currentPath) {
		rootBlock.value = null
		return
	}

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
	loadedPath = currentPath
}

function resolveCurrentPath(): string | undefined {
	const { pageRoute } = route.params as { pageRoute: string[] }
	// registered page routes carry isDynamic meta; their record path is the page's route pattern
	if (route.meta?.isDynamic) return route.matched?.[0]?.path
	if (pageRoute) return pageRoute[0]
	return "/"
}

watch(() => route.path, handleRouteChange, { immediate: true })

if (window.is_preview) useLivePreview(page, loadPage)

usePageMeta(() => {
	return {
		title: page.value?.page_title,
	}
})
</script>
