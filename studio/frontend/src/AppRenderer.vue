<template>
	<div class="h-full">
		<FrappeUIProvider>
			<!-- one page instance per page: a different page, or a preview reload, mounts fresh -->
			<router-view v-slot="{ Component, route }">
				<component :is="Component" :key="`${route.meta.pageName}:${revision}`" />
			</router-view>
			<!-- shows itself only when the page mounts a variant set; Keep is gated on can_edit_app -->
			<VariantsViewerPill />
		</FrappeUIProvider>
	</div>
</template>

<script setup lang="ts">
import { defineAsyncComponent, provide } from "vue"
import { FrappeUIProvider } from "frappe-ui"
import { useLivePreview } from "@/utils/useLivePreview"
import { usePageRefresh } from "@/utils/usePageRefresh"

const VariantsViewerPill = defineAsyncComponent(() => import("@/components/VariantsViewerPill.vue"))

// one way to re-read the open page: the socket drives it on the dev route, the variants pill
// calls it after a Keep, and both routes remount through the same revision
const { revision, refreshPage } = usePageRefresh()
provide("refreshPage", refreshPage)
if (window.is_preview) useLivePreview(refreshPage)
</script>
