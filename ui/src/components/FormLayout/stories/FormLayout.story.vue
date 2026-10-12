<template>
	<div class="flex flex-col h-screen">
		<Tabs v-model="activeTab" :tabs="tabs">
			<template #tab-panel="{ tab }">
				<StaticSchema v-if="tab.key === 'static'" />
				<FileUpload v-else-if="tab.key === 'fileupload'" />
			</template>
		</Tabs>
	</div>
</template>

<script setup lang="ts">
import { ref } from "vue";
import { Tabs } from "frappe-ui";
import StaticSchema from "./StaticSchema.story.vue";
import FileUpload from "../../FileUpload/stories/FileUpload.story.vue";

// The `useDoctypeLayout` / `useScriptedLayout` / meta-script panels are gone
// with the composables themselves — nothing shipped consumed them, and the
// meta path a real app uses is the stored Form Layout one
// (`experimental/FormLayoutSource`), exercised in the consuming app.
const tabs = [
	{ key: "static", label: "Hand-written schema" },
	{ key: "fileupload", label: "File upload" },
];
const activeTab = ref(0);
</script>
