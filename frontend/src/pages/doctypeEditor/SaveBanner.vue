<!-- What the last save says above the canvas: a refusal not shown at a field or section, a stale
     or half-written save, a failed file export, or a new DocType's first save. -->
<template>
	<Alert
		v-if="banner"
		class="mb-6"
		:theme="banner.failed ? 'red' : 'gray'"
		:title="banner.title"
		:primary-action="action"
		dismissible
		data-editor-save-banner
		@dismiss="save.banner.value = null"
	>
		<template v-if="banner.messages.length" #description>
			<p v-for="message in banner.messages" :key="message">{{ message }}</p>
		</template>
	</Alert>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { Alert } from "frappe-ui";
import { acts } from "@/acts/dispatcher";
import { __ } from "@/i18n";
import type { EditorSave, SaveOffer } from "./editorSave";

const props = defineProps<{ save: EditorSave; doctype: string }>();

const LABELS: Record<SaveOffer, string> = {
	"editor.reload_and_reapply": "Reload and re-apply my edits",
	"editor.write_files_again": "Write files again",
	"editor.open_list": "Open list",
};

const banner = computed(() => {
	const shown = props.save.banner.value;
	return shown?.doctype === props.doctype ? shown : null;
});
const action = computed(() => {
	const offer = banner.value?.offers[0];
	return offer ? { label: __(LABELS[offer]), onClick: () => acts.perform(offer) } : undefined;
});
</script>
