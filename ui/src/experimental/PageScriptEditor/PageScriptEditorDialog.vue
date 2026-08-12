<template>
	<!-- The editor as a dialog, so a script author can stay on the record they
	     are customizing and watch it replay behind the dialog. The pane itself is
	     layout-agnostic; a host route renders the same component full-width. -->
	<Dialog v-model="isOpen" :options="{ title: `Page scripts for ${dt}`, size: '5xl' }">
		<template #body-content>
			<PageScriptEditor :dt="dt" />
		</template>
	</Dialog>
</template>

<script setup lang="ts">
import { Dialog } from "frappe-ui";
import PageScriptEditor from "./PageScriptEditor.vue";

defineProps<{ dt: string }>();

const isOpen = defineModel<boolean>({ default: false });
</script>
