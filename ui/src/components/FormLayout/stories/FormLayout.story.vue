<template>
	<div class="flex flex-col h-screen">
		<Tabs v-model="activeTab" :tabs="tabs">
			<template #tab-panel="{ tab }">
				<StaticSchema v-if="tab.key === 'static'" />
				<DoctypeLayout v-else-if="tab.key === 'doctype'" :doctype="doctype" />
				<MetaScript v-else-if="tab.key === 'metascript'" />
				<ScriptedDoctypeLayout v-else-if="tab.key === 'scripteddoctype'" doctype="ToDo" />
				<FileUpload v-else-if="tab.key === 'fileupload'" />
			</template>
		</Tabs>
	</div>
</template>

<script setup lang="ts">
import { ref } from "vue";
import { Tabs } from "frappe-ui";
import StaticSchema from "./StaticSchema.story.vue";
import DoctypeLayout from "./DoctypeLayout.story.vue";
import MetaScript from "./MetaScript.story.vue";
import ScriptedDoctypeLayout from "./ScriptedDoctypeLayout.story.vue";
import FileUpload from "./FileUpload.story.vue";
import { useDoctypeLayout } from "../useDoctypeLayout";

const doctype = "CRM Deal";

// Warm the memo cache up-front so the meta resolves while the default tab is
// active. When a panel later mounts it reads the cached layout — no async
// update fires inside a TabsContent mid-transition (which crashed reka-ui).
useDoctypeLayout(doctype);
useDoctypeLayout("ToDo"); // for the useScriptedLayout('ToDo') panel

const tabs = [
	{ key: "static", label: "Hand-written schema" },
	{ key: "doctype", label: `useDoctypeLayout('${doctype}')` },
	{ key: "metascript", label: "Meta script" },
	{ key: "scripteddoctype", label: `useScriptedLayout('ToDo')` },
	{ key: "fileupload", label: "File upload" },
];
const activeTab = ref(0);
</script>
