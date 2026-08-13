<template>
	<!-- The editor as a dialog, so a script author can stay on the record they
	     are customizing and watch it replay behind it. The accepted cost, measured
	     rather than assumed (ticket 23): Dialog's focus trap leaves that record
	     visible but unclickable while the editor is open.

	     `bare` is the SettingsDialog pattern — Dialog owns the overlay, focus trap
	     and escape; the panel owns its geometry. Width still passes through
	     Dialog's `size` (a max-w-* cap), so `7xl` is as wide as it goes; the panel
	     takes all of it, and owns the height Dialog never sets. -->
	<Dialog v-model="isOpen" bare size="7xl">
		<div
			class="flex h-[92vh] w-full flex-col overflow-hidden rounded-xl bg-surface-elevation-1"
		>
			<PageScriptEditor :dt="dt" :replaysOn="replaysOn" :onClose="close" />
		</div>
	</Dialog>
</template>

<script setup lang="ts">
import { Dialog } from "frappe-ui";
import PageScriptEditor from "./PageScriptEditor.vue";

defineProps<{
	dt: string;
	/** The record the editor is opened over, named in its saved-state line. */
	replaysOn?: string;
}>();

const isOpen = defineModel<boolean>({ default: false });

function close() {
	isOpen.value = false;
}
</script>
