<template>
	<div class="flex flex-col gap-3">
		<!-- Interpreted page script: only for non-exported apps (exported pages come from code) -->
		<PageScript v-if="!store.activeApp?.is_standard" :page="page" />
	</div>
</template>

<script setup lang="ts">
import useStudioStore from "@/stores/studioStore"
import type { StudioPage } from "@/types/Studio/StudioPage"
import PageScript from "@/components/PageScript.vue"

defineProps<{
	page: StudioPage
}>()

const store = useStudioStore()
</script>
