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
			})
		})
	} catch (error) {
		console.error("Error fetching dynamic routes:", error)
	}
}

watch(
	[() => route.params?.appRoute, () => route.params?.pageRoute],
	async ([appRoute, pageRoute]) => {
		if (appRoute === "studio") return

		if (pageRoute) {
			page.value = await findPageWithRoute(appRoute, pageRoute)
			const blocks = jsonToJs(page.value.blocks)
			if (blocks) {
				rootBlock.value = getBlockInstance(blocks[0])
			}
			await store.setPageResources(page.value)
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
	if (route.params?.appRoute && route.params?.appRoute !== "studio") {
		await addDynamicRoutes(route.params?.appRoute)
	}
})
</script>
