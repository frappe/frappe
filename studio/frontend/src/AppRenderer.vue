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
import { defineAsyncComponent, ref } from "vue"
import { FrappeUIProvider } from "frappe-ui"
import { useLivePreview } from "@/utils/useLivePreview"

const VariantsViewerPill = defineAsyncComponent(() => import("@/components/VariantsViewerPill.vue"))

const revision = window.is_preview ? useLivePreview() : ref(0)
</script>
