<!-- The shell's own dialog stack, for `shell.dialog.open`: the host `page.dialog.open` uses, above any page. -->
<template>
	<PageOpenDialog v-for="entry in shellDialogs.entries.value" :key="entry.id" :entry="entry" />
</template>

<script setup lang="ts">
import PageOpenDialog from "./dialogs/PageOpenDialog.vue";
import { shellDialogs } from "./dialog";
</script>
