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

<script setup>
import { ref, watchEffect } from "vue"
import { useRoute } from "vue-router"
import { doctypesBySlug, workspacesBySlug, modulesBySlug } from "@/data/permissions"

import ModuleSidebar from "@/components/ModuleSidebar.vue"
import Navbar from "@/components/Navbar.vue"

const route = useRoute()
const module = ref("")
const isSidebarCollapsed = ref(false)

// set module based on route. Using watchEffect since this needs to track multiple route params
watchEffect(() => {
	if (route.params?.module) {
		module.value = modulesBySlug[route.params.module]
	} else if (route.params?.doctype) {
		module.value = doctypesBySlug[route.params.doctype].module
	} else if (route.params?.workspace && !module.value) {
		module.value = workspacesBySlug[route.params.workspace].module
	}
})
</script>
