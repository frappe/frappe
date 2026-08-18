<template>
	<!-- The page's own dialog stack, mounted inside the Record page it belongs
	     to. `confirm` and `danger` are not here — frappe-ui renders those on its
	     own stack; only `open` and `form` need a host. -->
	<component
		:is="entry.kind === 'form' ? PageFormDialog : PageOpenDialog"
		v-for="entry in controller.dialogs.value"
		:key="entry.id"
		:entry="entry"
	/>
</template>

<script setup lang="ts">
import { onUnmounted } from "vue";
import PageFormDialog from "./PageFormDialog.vue";
import PageOpenDialog from "./PageOpenDialog.vue";
import type { RecordPageController } from "./createRecordPage";

const props = defineProps<{ controller: RecordPageController }>();

// The page binding: this component lives inside the record page, so its unmount
// *is* navigating away. Every open dialog closes newest-first, each promise
// resolving `null` — an awaiting script can never hang on a dialog the reader
// can no longer see.
onUnmounted(() => props.controller.closeDialogs());
</script>
