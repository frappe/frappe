<template>
	<!-- Every app browses its own source files in one tree: on disk for a repository app, in the
	     file store for a database app, with each page's script listed beside its page. -->
	<div>
		<FileExplorer />
	</div>
</template>

<script setup lang="ts">
import FileExplorer from "@/components/FileExplorer.vue"
</script>
