<template>
	<div class="flex flex-row">
		<ModuleSidebar
			v-if="module"
			:isCollapsed="isSidebarCollapsed"
			:module="module"
			@toggleSidebar="isSidebarCollapsed = !isSidebarCollapsed"
		/>
		<div class="flex flex-col" :class="isSidebarCollapsed ? 'w-[1380px]' : 'w-[1200px]'">
			<Navbar />
			<router-view />
		</div>
	</div>
</template>

<script setup lang="ts">
import { ref, watchEffect } from "vue"
import { doctypesBySlug, workspacesBySlug, modulesBySlug } from "@/data/permissions"

import ModuleSidebar from "@/components/ModuleSidebar.vue"
import Navbar from "@/components/Navbar.vue"
import { useRouteParamsAsStrings } from "@/composables/router"

const routeParams = useRouteParamsAsStrings()
const module = ref("")
const isSidebarCollapsed = ref(false)

// set module based on route. Using watchEffect since this needs to track multiple route params
watchEffect(() => {
	if (routeParams?.module) {
		module.value = modulesBySlug[routeParams.module]
	} else if (routeParams?.doctype) {
		module.value = doctypesBySlug[routeParams.doctype]?.module
	} else if (routeParams?.workspace && !module.value) {
		module.value = workspacesBySlug[routeParams.workspace]?.module
	}
})
</script>
