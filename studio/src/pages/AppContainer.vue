<template>
	<AppComponent v-if="rootBlock" :block="rootBlock" />
</template>

<script setup lang="ts">
import { watch, ref, h } from "vue"
import { useRoute } from "vue-router"
import useStore from "@/store"

import { getBlockInstance, jsonToJs } from "@/utils/helpers"
import AppComponent from "@/components/AppComponent.vue"

const route = useRoute()
const rootBlock = ref(null)
const store = useStore()

watch(
	() => route.params?.pageRoute,
	async () => {
		const pageRoute = route.params?.pageRoute
		if (pageRoute) {
			const page = await store.findPageWithRoute(pageRoute)
			const blocks = jsonToJs(page.blocks)
			if (blocks) {
				rootBlock.value = getBlockInstance(blocks[0])
			}
		}
	},
	{ immediate: true },
)
</script>
