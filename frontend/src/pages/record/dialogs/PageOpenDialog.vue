<!-- `page.dialog.open()`'s host: the chrome is the host's, so Esc, the backdrop and the X
     resolve `null`; the component renders the body and answers with `close(result)`. -->
<template>
	<Dialog
		v-model:open="isOpen"
		:title="entry.options.title"
		:size="size"
		:dismissible="dismissible"
		:show-close-button="dismissible"
		@after-leave="entry.dismiss()"
	>
		<component :is="entry.component" v-bind="entry.props" :close="close" />
	</Dialog>
</template>

<script setup lang="ts">
import { ref, watch } from "vue";
import { Dialog } from "frappe-ui";
import type { DialogSize } from "frappe-ui";
import type { PageDialogEntry } from "@/recordPage/dialog";

const props = defineProps<{ entry: PageDialogEntry }>();

const isOpen = ref(true);
const dismissible = props.entry.options.dismissible !== false;
const size = (props.entry.options.size as DialogSize) ?? "md";

// Settled now, not on `after-leave`: a page unmounting mid-transition must not report a dismissal.
function close(value: any = null) {
	props.entry.settle(value);
	isOpen.value = false;
}

// `settle` is idempotent, so a close that already answered wins over this.
watch(isOpen, (open) => {
	if (!open) props.entry.settle(null);
});
</script>
