<template>
	<slot v-if="pageScope.pageScriptReady" />
</template>

<script setup lang="ts">
import { usePageScope } from "@/stores/codeStore"

// Run the page script during this component's setup so Vue lifecycle hooks and effects belong
// to this instance. Key the host by pageScriptVersion to clean up the old instance on edits.
// Wait for async setup bindings before rendering the slot.
const pageScope = usePageScope()
pageScope.runPageSetup()
</script>
