<template>
	<AppComponent :block="root" />
</template>

<script setup lang="ts">
import { watch, provide, onUnmounted } from "vue"
import { useRouter } from "vue-router"
import { usePageMeta } from "frappe-ui"

import { takePreparedPage } from "@/router/pageLoader"
import { onPageScriptHotUpdate } from "@/data/studioPageScripts"
import AppComponent from "@/components/AppComponent.vue"

import useAppStore from "@/stores/appStore"
import useComponentStore from "@/stores/componentStore"
import { pageScopeKey } from "@/stores/codeStore"

const router = useRouter()
const { page, scope, pageRoute, root } = takePreparedPage(router.currentRoute.value.fullPath)

// the page's own route: follows param changes on this page only, so leaving it never refetches
// its resources with the next page's params
watch(router.currentRoute, (to) => {
	if (to.meta.pageName === page.name) pageRoute.value = to
})

provide(pageScopeKey, scope)
onUnmounted(() => scope.teardownPage())
onUnmounted(onPageScriptHotUpdate((name, setup) => scope.applyPageScriptHotUpdate(name, setup)))

useAppStore().activePage = page
useComponentStore().setComponents(page.components || [])
usePageMeta(() => ({ title: page.page_title }))
</script>
