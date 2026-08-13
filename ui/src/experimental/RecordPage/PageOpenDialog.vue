<template>
	<!-- `page.dialog.open()`'s host. The chrome is the host's, so Esc, the
	     backdrop and the X resolve `null` for a component that never thought
	     about dismissal; the component renders the body and answers with
	     `close(result)`. -->
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
import type { PageDialogEntry } from "./dialog";

const props = defineProps<{ entry: PageDialogEntry }>();

const isOpen = ref(true);
const dismissible = props.entry.options.dismissible !== false;
const size = (props.entry.options.size as DialogSize) ?? "md";

// The promise settles here, not on `after-leave`: the answer is known now, and
// waiting for the transition would let a page unmounting in that window report
// the reader's answer as a dismissal.
function close(value: any = null) {
	props.entry.settle(value);
	isOpen.value = false;
}

// Esc, the backdrop and the X only flip `isOpen`. `settle` is idempotent, so a
// close that already answered wins and this covers every other way out.
watch(isOpen, (open) => {
	if (!open) props.entry.settle(null);
});
</script>
