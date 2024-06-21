<template>
	<div class="flex flex-row">
		<ModuleSidebar v-if="module" :module="module" />
		<div class="flex grow flex-col">
			<Navbar />
			<router-view />
		</div>
	</div>
</template>

<script setup lang="ts">
import { ref, watchEffect } from "vue"
import { useRoute } from "vue-router"
import { doctypesBySlug, workspacesBySlug, modulesBySlug } from "@/data/permissions"

import ModuleSidebar from "@/components/ModuleSidebar.vue"
import Navbar from "@/components/Navbar.vue"
import { useRouteParamsAsStrings } from "@/composables/router"

const routeParams = useRouteParamsAsStrings()
const module = ref("")

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
