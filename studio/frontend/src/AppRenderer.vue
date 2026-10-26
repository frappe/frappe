<template>
	<div class="h-full">
		<FrappeUIProvider>
			<!-- one page instance per page: a different page, or a preview reload, mounts fresh -->
			<router-view v-slot="{ Component, route }">
				<component :is="Component" :key="`${route.meta.pageName}:${revision}`" />
			</router-view>
			<SwitcherPill v-if="showReviewChrome" />
		</FrappeUIProvider>
	</div>
</template>

<script setup lang="ts">
import { ref } from "vue"
import { FrappeUIProvider } from "frappe-ui"
import { useLivePreview } from "@/utils/useLivePreview"
import SwitcherPill from "@/components/SwitcherPill.vue"

// review chrome (the variants pill) shows where apps are developed —
// dev benches; a published app on a production site stays clean
const showReviewChrome = Boolean((window as any).is_developer_mode)
const revision = window.is_preview ? useLivePreview() : ref(0)
</script>
