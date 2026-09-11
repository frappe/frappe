<!-- The page's own dialog stack: `open` and `form` need a host; `confirm` and `danger`
     render on frappe-ui's own stack. -->
<template>
	<component
		:is="entry.kind === 'form' ? PageFormDialog : PageOpenDialog"
		v-for="entry in controller.dialogs.value"
		:key="entry.id"
		:entry="entry"
	/>
</template>

<script setup lang="ts">
import { onUnmounted } from "vue";
import type { RecordPageController } from "@/recordPage";
import PageFormDialog from "./PageFormDialog.vue";
import PageOpenDialog from "./PageOpenDialog.vue";

const props = defineProps<{ controller: RecordPageController }>();

// Unmounting is navigating away: every open dialog resolves `null`, so no script hangs on it.
onUnmounted(() => props.controller.closeDialogs());
</script>
