<template>
	<PageScriptHost :key="scope.pageScriptVersion">
		<AppComponent :block="root" />
	</PageScriptHost>
</template>

<script setup lang="ts">
import { provide, onUnmounted } from "vue"
import { usePageMeta } from "frappe-ui"

import { useLoadedPage } from "@/runtime/page/pageLoader"
import { onPageScriptHotUpdate } from "@/runtime/data/studioPageScripts"
import AppComponent from "@/runtime/components/AppComponent.vue"
import PageScriptHost from "@/runtime/components/PageScriptHost.vue"

import useAppStore from "@/runtime/stores/appStore"
import { pageScopeKey } from "@/runtime/stores/codeStore"

const { page, scope, root } = useLoadedPage()

provide(pageScopeKey, scope)
onUnmounted(() => scope.teardownPage())
onUnmounted(onPageScriptHotUpdate((name, setup) => scope.applyPageScriptHotUpdate(name, setup)))

useAppStore().activePage = page
usePageMeta(() => ({ title: page.tab_title ? scope.evaluateDynamicValues(page.tab_title) : page.page_title }))
</script>
