<template>
	<div class="flex flex-row">
		<ModuleSidebar v-if="moduleSlug" :module="moduleSlug" />
		<div class="flex grow flex-col">
			<Navbar />
			<router-view></router-view>
		</div>
	</div>
</template>

<script setup>
import { ref, watch, inject } from "vue"
import { useRoute } from "vue-router"
import { createResource } from "frappe-ui"
import { slug } from "@/utils/routing"

import ModuleSidebar from "@/components/ModuleSidebar.vue"
import Navbar from "@/components/Navbar.vue"

const route = useRoute()
const permissions = inject("$permissions")

const moduleSlug = ref("")

const workspaceModule = createResource({
	url: "frappe.api.desk.get_workspace_module",
})

watch(
	() => route.params?.module,
	(module) => {
		if (!module) return
		moduleSlug.value = module
	},
	{ immediate: true }
)

watch(
	() => route.params?.name,
	async (name) => {
		if (name && !moduleSlug.value) {
			const workspace = permissions.workspacesBySlug[name]
			await workspaceModule.submit({ workspace: workspace })
			moduleSlug.value = slug(workspaceModule.data)
		}
	},
	{ immediate: true }
)
</script>
