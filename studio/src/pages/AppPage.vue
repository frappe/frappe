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
import { pageScopeKey } from "@/stores/codeStore"

const { page, scope, root } = useLoadedPage()

provide(pageScopeKey, scope)
onUnmounted(() => scope.teardownPage())
onUnmounted(onPageScriptHotUpdate((name, setup) => scope.applyPageScriptHotUpdate(name, setup)))

useAppStore().activePage = page
const tabTitle = page.tab_title
if (tabTitle) usePageMeta(() => ({ title: scope.evaluateDynamicValues(tabTitle) || page.page_title }))
</script>
