<template>
	<div class="flex flex-col gap-3">
		<!-- Exported apps live in code: browse/edit the on-disk studio/<app>/ files.
		     Non-exported apps store their logic in the interpreted page script. -->
		<FileExplorer v-if="store.activeApp?.is_standard" />
		<PageScript v-else />
	</div>
</template>

<script setup lang="ts">
import useStudioStore from "@/stores/studioStore"
import PageScript from "@/components/PageScript.vue"
import FileExplorer from "@/components/FileExplorer.vue"

const store = useStudioStore()
</script>
