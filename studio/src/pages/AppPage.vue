<template>
	<AppComponent :block="root" />
</template>

<script setup lang="ts">
import { provide, onUnmounted } from "vue"
import { usePageMeta } from "frappe-ui"

import { useLoadedPage } from "@/page/pageLoader"
import { onPageScriptHotUpdate } from "@/data/studioPageScripts"
import AppComponent from "@/components/AppComponent.vue"

import useAppStore from "@/stores/appStore"
import useComponentStore from "@/stores/componentStore"
import { pageScopeKey } from "@/stores/codeStore"

const { page, scope, root } = useLoadedPage()

provide(pageScopeKey, scope)
onUnmounted(() => scope.teardownPage())
onUnmounted(onPageScriptHotUpdate((name, setup) => scope.applyPageScriptHotUpdate(name, setup)))

useAppStore().activePage = page
useComponentStore().setComponents(page.components || [])
usePageMeta(() => ({ title: page.page_title }))
</script>
