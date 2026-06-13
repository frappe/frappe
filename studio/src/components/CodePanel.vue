<template>
	<div class="flex flex-col gap-3">
		<!-- Exported apps live in code: browse/edit the on-disk studio/<app>/ files.
		     Non-exported apps store their logic in the interpreted page script. -->
		<FileExplorer v-if="store.activeApp?.is_standard" :app="store.activeApp" />
		<PageScript v-else :page="page" />
	</div>
</template>

<script setup lang="ts">
import useStudioStore from "@/stores/studioStore"
import type { StudioPage } from "@/types/Studio/StudioPage"
import PageScript from "@/components/PageScript.vue"
import FileExplorer from "@/components/FileExplorer.vue"

defineProps<{
	page: StudioPage
}>()

const store = useStudioStore()
</script>
