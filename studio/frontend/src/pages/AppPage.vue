<template>
	<PageScriptHost :key="scope.pageScriptVersion">
		<AppComponent :block="root" />
	</PageScriptHost>
</template>

<script setup lang="ts">
import { computed, inject, provide, onUnmounted, watch } from "vue"
import { usePageMeta } from "frappe-ui"

import { useLoadedPage } from "@/page/pageLoader"
import { onPageScriptHotUpdate } from "@/data/studioPageScripts"
import AppComponent from "@/components/AppComponent.vue"
import PageScriptHost from "@/components/PageScriptHost.vue"

import useAppStore from "@/stores/appStore"
import { pageScopeKey } from "@/stores/codeStore"

const { page, scope, root } = useLoadedPage()

provide(pageScopeKey, scope)
onUnmounted(() => scope.teardownPage())
onUnmounted(onPageScriptHotUpdate((name, setup) => scope.applyPageScriptHotUpdate(name, setup)))

useAppStore().activePage = page
const title = computed(() => (page.tab_title ? scope.evaluateDynamicValues(page.tab_title) : page.page_title))
const reportTitle = inject<((title: string) => void) | null>("reportTitle", null)
if (reportTitle) watch(title, reportTitle, { immediate: true })
else usePageMeta(() => ({ title: title.value }))
</script>
