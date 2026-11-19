<!-- The Editor / Settings / Preview strip below the page header, drawn like the record page's tab strip. -->
<template>
	<Tabs
		:modelValue="tab"
		class="shrink-0"
		:class="TAB_STRIP_CLASSES"
		data-act="editor.open_tab"
		@update:modelValue="acts.perform('editor.open_tab', $event)"
	>
		<TabList variant="underline">
			<TabTrigger
				v-for="one in EDITOR_TABS"
				:key="one.value"
				:value="one.value"
				:label="__(one.label)"
				:icon-left="one.icon"
			/>
		</TabList>
	</Tabs>
</template>

<script setup lang="ts">
import { TabList, Tabs, TabTrigger } from "frappe-ui";
import { acts } from "@/acts/dispatcher";
import { __ } from "@/i18n";
import { TAB_STRIP_CLASSES } from "@/pages/record/tabs/recordTabs";
import { EDITOR_TABS } from "./editorActs";
import type { EditorTab } from "./pendingEdits";

const tab = defineModel<EditorTab>({ required: true });
</script>
