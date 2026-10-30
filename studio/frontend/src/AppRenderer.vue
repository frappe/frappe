<template>
	<div class="h-full">
		<FrappeUIProvider>
			<!-- one page instance per page: a different page, or a preview reload, mounts fresh -->
			<router-view v-slot="{ Component, route }">
				<component :is="Component" :key="`${route.meta.pageName}:${pageRevision}`" />
			</router-view>
			<!-- shows itself only when the page mounts a variant set; Keep is gated on can_edit_app -->
			<VariantsViewerPill />
		</FrappeUIProvider>
	</div>
</template>

<script setup lang="ts">
import { defineAsyncComponent, provide } from "vue"
import { useRouter } from "vue-router"
import { FrappeUIProvider } from "frappe-ui"
import { pageRevision, refreshPageKey, reloadCurrentPage } from "@/page/pageLoader"
import { useLivePreview } from "@/utils/useLivePreview"

const VariantsViewerPill = defineAsyncComponent(() => import("@/components/VariantsViewerPill.vue"))

// one way to re-read the open page: the socket drives it on the dev route and the variants
// pill calls it after a Keep, and the loader's revision remounts the page for both
const router = useRouter()
const refreshPage = () => reloadCurrentPage(router)
provide(refreshPageKey, refreshPage)
if (window.is_preview) useLivePreview(refreshPage)
</script>
