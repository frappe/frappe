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
import useComponentStore from "@/stores/componentStore"

import type { StudioPage } from "@/types/Studio/StudioPage"
import Block from "@/utils/block"

const store = useAppStore()
const route = useRoute()
const codeStore = useCodeStore()
const componentStore = useComponentStore()
const page = ref<StudioPage | null>(null)

const rootBlock = ref<Block | null>(null)

let loadedPath: string | null = null
async function handleRouteChange() {
	const currentPath = resolveCurrentPath()
	if (currentPath && currentPath === loadedPath && page.value) {
		// param-only navigation (/articles/a -> /articles/b)
		return
	}
	await loadPage()
}

let loadToken = 0
async function loadPage() {
	const token = ++loadToken
	const currentPath = resolveCurrentPath()
	if (!currentPath) {
		rootBlock.value = null
		return
	}
	codeStore.beginPageSwitch()

	page.value = await findPageWithRoute(window.app_name, currentPath, Boolean(window.is_preview))
	if (token !== loadToken) return
	if (!page.value) {
		rootBlock.value = null
		codeStore.endPageSwitch()
		return
	}
	componentStore.setComponents(page.value.components || [])
	await store.setPageData(page.value)
	await codeStore.setPageScript(page.value, Boolean(page.value.is_standard))
	if (token !== loadToken) return

	const blocks = JSON.parse(page.value?.blocks)
	if (blocks) {
		rootBlock.value = getBlockInstance(blocks[0])
	}
	// same tick as the swap, so the new tree's first render sees its own context
	codeStore.endPageSwitch()
	loadedPath = currentPath
}

function resolveCurrentPath(): string | undefined {
	// by page, not matched path: an alias record's path is the alias, and the server looks up the page's own route
	const pageName = route.matched[0]?.meta?.pageName
	return window.app_pages.find((page) => page.name === pageName)?.route
}

watch(() => route.path, handleRouteChange, { immediate: true })

if (window.is_preview) useLivePreview(page, loadPage)

usePageMeta(() => {
	return {
		title: page.value?.page_title,
	}
})
</script>
