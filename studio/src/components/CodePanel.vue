<template>
	<div class="flex flex-col gap-3">
		<!-- Interpreted page script: only for non-exported apps (exported pages come from code) -->
		<PageScript v-if="!store.activeApp?.is_standard" :page="page" />
		<template v-if="store.activeApp?.frappe_app">
			<ModulesPanel
				v-if="store.activePage"
				scope="page"
				parentDoctype="Studio Page"
				:parentName="store.activePage.name"
				:frappeApp="store.activeApp.frappe_app"
				:key="`page-modules-${store.selectedPage ?? ''}`"
			/>
			<ModulesPanel
				scope="app"
				parentDoctype="Studio App"
				:parentName="store.activeApp.name"
				:frappeApp="store.activeApp.frappe_app"
				:key="`app-modules-${store.activeApp.name}`"
			/>
		</template>
	</div>
</template>

<script setup lang="ts">
import useStudioStore from "@/stores/studioStore"
import type { StudioPage } from "@/types/Studio/StudioPage"
import PageScript from "@/components/PageScript.vue"
import ModulesPanel from "@/components/ModulesPanel.vue"

defineProps<{
	page: StudioPage
}>()

const store = useStudioStore()
</script>
