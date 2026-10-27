<template>
	<div class="h-full">
		<FrappeUIProvider>
			<!-- one page instance per page: a different page, or a preview reload, mounts fresh -->
			<router-view v-slot="{ Component, route }">
				<component :is="Component" :key="`${route.meta.pageName}:${revision}`" />
			</router-view>
			<VariantsViewerPill v-if="showReviewChrome" />
		</FrappeUIProvider>
	</div>
</template>

<script setup lang="ts">
import { defineAsyncComponent, ref } from "vue"
import { FrappeUIProvider } from "frappe-ui"
import { useLivePreview } from "@/utils/useLivePreview"

// review chrome shows where apps are developed — dev benches; a published
// app on a production site stays clean and never loads it
const showReviewChrome = Boolean((window as any).is_developer_mode)
const VariantsViewerPill = defineAsyncComponent(() => import("@/components/VariantsViewerPill.vue"))
const revision = window.is_preview ? useLivePreview() : ref(0)
</script>
