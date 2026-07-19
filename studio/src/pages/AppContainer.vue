<template>
	<AppComponent v-if="rootBlock" :block="rootBlock" />
</template>

<script setup lang="ts">
import { watch, ref, inject, onMounted, onBeforeUnmount } from "vue"
import { useRoute } from "vue-router"
import { usePageMeta } from "frappe-ui"
import { useDebounceFn } from "@vueuse/core"

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

async function loadPage() {
	let { pageRoute } = route.params as { pageRoute: string[] }
	const isDynamic = route.meta?.isDynamic

	let currentPath = "/"
	if (isDynamic) {
		currentPath = route.matched?.[0]?.path
	} else if (pageRoute) {
		currentPath = pageRoute[0]
	}

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
}

watch(() => route.path, loadPage, { immediate: true })

// Live preview: re-render when the open page changes in the DB — an editor save, an AI edit, or a
// disk edit. Debounced so a burst of autosaves coalesces into one reload. Socket is provided only
// in preview (renderer.ts), so this is inert for a published app.
const socket = inject<any>("socket")
const reloadPage = useDebounceFn(loadPage, 300)
const onDocUpdate = (info: any) => {
	if (info?.doctype === "Studio Page" && info?.name === page.value?.name) reloadPage()
}

onMounted(() => socket?.on("studio_doc_update", onDocUpdate))
onBeforeUnmount(() => socket?.off("studio_doc_update", onDocUpdate))

usePageMeta(() => {
	return {
		title: page.value?.page_title,
	}
})
</script>
