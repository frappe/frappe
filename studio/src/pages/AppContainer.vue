<template>
	<AppComponent v-if="rootBlock" :block="rootBlock" />
</template>

<script setup lang="ts">
import { watch, ref } from "vue"
import { useRoute } from "vue-router"
import { usePageMeta } from "frappe-ui"

import { fetchAppPage } from "@/utils/helpers"
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

let loadedPageName: string | null = null
async function handleRouteChange() {
	const pageName = getCurrentPageName()
	// same page, different params (/articles/a -> /articles/b): keep it loaded
	if (pageName && pageName === loadedPageName && page.value) return
	await loadPage()
}

let loadToken = 0
async function loadPage() {
	const token = ++loadToken
	const pageName = getCurrentPageName()
	if (!pageName) {
		rootBlock.value = null
		return
	}
	codeStore.activeScope.teardownPage()

	page.value = await fetchAppPage(window.app_name, pageName, Boolean(window.is_preview))
	if (token !== loadToken || !page.value) return
	componentStore.setComponents(page.value.components || [])
	const scope = await loadPageScope(page.value)
	if (token !== loadToken) return scope.teardownPage()

	// same tick as the block swap, so the old blocks never render against the new page's data
	codeStore.activatePageScope(scope)
	const blocks = JSON.parse(page.value?.blocks)
	if (blocks) {
		rootBlock.value = getBlockInstance(blocks[0])
	}
	loadedPageName = pageName
}

async function loadPageScope(page: StudioPage) {
	const scope = codeStore.createPageScope()
	try {
		await store.setPageData(page, scope)
		await scope.setPageScript(page, Boolean(page.is_standard))
		return scope
	} catch (error) {
		scope.teardownPage()
		throw error
	}
}

function getCurrentPageName(): string | undefined {
	return route.meta.pageName as string | undefined
}

// sync: tear down the page we are leaving before its resources refetch with the next page's params
watch(() => route.path, handleRouteChange, { immediate: true, flush: "sync" })

if (window.is_preview) useLivePreview(page, loadPage)

usePageMeta(() => {
	return {
		title: page.value?.page_title,
	}
})
</script>
