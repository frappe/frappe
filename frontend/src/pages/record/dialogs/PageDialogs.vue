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
import { provide } from "vue";
import { CodeErrorsKey, FieldErrorsKey } from "@framework/ui/fields/types";
import type { RecordPageController } from "@/recordPage";
import PageFormDialog from "./PageFormDialog.vue";
import PageOpenDialog from "./PageOpenDialog.vue";

defineProps<{ controller: RecordPageController }>();

// A dialog's form is not the record's, so the record's compile and field errors stop here.
provide(CodeErrorsKey, null);
provide(FieldErrorsKey, null);
</script>
