<template>
	<div class="flex flex-col gap-3">
		<!-- Exported apps live in code: browse/edit the on-disk studio/<app>/ files.
		     Non-exported apps keep their page and router scripts in the DB. -->
		<FileExplorer v-if="store.activeApp?.is_standard" />
		<CustomAppScript v-else />
	</div>
</template>

<script setup lang="ts">
import useStudioStore from "@/stores/studioStore"
import CustomAppScript from "@/components/CustomAppScript.vue"
import FileExplorer from "@/components/FileExplorer.vue"

const store = useStudioStore()
</script>
