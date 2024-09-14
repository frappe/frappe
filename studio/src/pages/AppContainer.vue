<template>
	<AppComponent v-if="rootBlock" :block="rootBlock" />
</template>

<script setup lang="ts">
import { watch, ref } from "vue"
import { useRoute } from "vue-router"
import { usePageMeta } from "frappe-ui"
import useStore from "@/store"

import { getBlockInstance, jsonToJs } from "@/utils/helpers"
import AppComponent from "@/components/AppComponent.vue"

const route = useRoute()
const store = useStore()
const page = ref(null)
const rootBlock = ref(null)

watch(
	() => route.params?.pageRoute,
	async () => {
		const pageRoute = route.params?.pageRoute
		if (pageRoute) {
			page.value = await store.findPageWithRoute(pageRoute)
			const blocks = jsonToJs(page.value.blocks)
			if (blocks) {
				rootBlock.value = getBlockInstance(blocks[0])
			}
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
