<template>
	<div class="flex flex-col gap-3">
		<!-- Every app browses its own source files: on disk for a repository app, in the file store
		     for a database app. A database app keeps its page scripts on the page doc rather than
		     in that store, so they open in the script dock from the explorer instead. -->
		<FileExplorer />
		<PageScript v-if="store.usesDbFiles && store.showPageScriptEditor" />
	</div>
</template>

<script setup lang="ts">
import useStudioStore from "@/stores/studioStore"
import PageScript from "@/components/PageScript.vue"
import FileExplorer from "@/components/FileExplorer.vue"

const store = useStudioStore()
</script>
