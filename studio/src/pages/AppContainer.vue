<template>
	<AppComponent v-if="rootBlock" :block="rootBlock" />
</template>

<script setup lang="ts">
import { watch, ref } from "vue"
import { useRoute } from "vue-router"
import { usePageMeta } from "frappe-ui"

import { getBlockInstance, jsonToJs, findPageWithRoute } from "@/utils/helpers"
import AppComponent from "@/components/AppComponent.vue"

import useAppStore from "@/stores/appStore"

const store = useAppStore()
const route = useRoute()
const page = ref(null)
const rootBlock = ref(null)

watch(
	() => route.params?.pageRoute,
	async (pageRoute, _) => {
		if (pageRoute === "studio") return

		if (pageRoute) {
			page.value = await findPageWithRoute(pageRoute)
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
</script>
