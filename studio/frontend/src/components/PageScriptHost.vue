<template>
	<slot v-if="pageScope.pageScriptReady" />
</template>

<script setup lang="ts">
import { usePageScope } from "@/stores/codeStore"

// Runs the page script's setup() inside this component's own setup(), so the script gets a real
// component instance: onMounted and the other lifecycle hooks fire, and the effects it creates
// are disposed when this host unmounts. Key the host on pageScriptVersion so a changed script
// gets a new instance. Slot content waits for an async setup, so bindings resolve before blocks
// render against them.
const pageScope = usePageScope()
pageScope.runPageSetup()
</script>
