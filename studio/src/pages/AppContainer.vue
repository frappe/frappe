<template>
	<AppComponent v-if="rootBlock" :block="rootBlock" />
</template>

<script setup lang="ts">
import { watch, ref, onMounted } from "vue"
import { useRoute, useRouter } from "vue-router"
import { usePageMeta } from "frappe-ui"

import { getBlockInstance, jsonToJs, findPageWithRoute, fetchAppPages } from "@/utils/helpers"
import AppComponent from "@/components/AppComponent.vue"

import useAppStore from "@/stores/appStore"

const store = useAppStore()
const route = useRoute()
const router = useRouter()
const page = ref(null)
const rootBlock = ref(null)

const addDynamicRoutes = async (appRoute) => {
	try {
		const pages = await fetchAppPages(appRoute)

		pages.forEach((page) => {
			router.addRoute({
				path: page.route.replace("studio-app", ""),
				name: page.page_title,
				component: () => import("@/pages/AppContainer.vue"),
				props: true,
				meta: {
					isDynamic: true,
					appRoute: appRoute,
				},
			})
		})

		router.replace(router.currentRoute.value.fullPath)
	} catch (error) {
		console.error("Error fetching dynamic routes:", error)
	}
}

watch(
	() => route.path,
	async () => {
		let { appRoute, pageRoute } = route.params
		const isDynamic = route.meta?.isDynamic
		if (appRoute === "studio") return

		let currentPath = ""
		if (isDynamic) {
			currentPath = route.matched?.[0]?.path
		} else if (pageRoute) {
			currentPath = pageRoute[0]
		}

		if (currentPath) {
			// find page with matched route
			page.value = await findPageWithRoute(appRoute, currentPath)
			if (!page.value) return
			const blocks = jsonToJs(page.value?.blocks)
			if (blocks) {
				rootBlock.value = getBlockInstance(blocks[0])
			}
			await store.setPageResources(page.value)
		} else {
			rootBlock.value = null
		}
	},
	{ immediate: true },
)

usePageMeta(() => {
	return {
		title: page.value?.page_title,
	}
})

onMounted(async () => {
	const appRoute = route.params?.appRoute || route.meta?.appRoute
	if (appRoute && appRoute !== "studio") {
		await addDynamicRoutes(appRoute)
	}
})
</script>
