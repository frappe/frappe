<template>
	<SettingsDialog v-model:tab="page.state.settingsTab" :groups="groups">
		<template #general><GeneralPanel /></template>
		<template v-for="spec in docSpecs" #[spec.key]>
			<DocPanel :spec="spec" :description="DESCRIPTIONS[spec.key]" />
		</template>
		<template #models><ModelsPanel /></template>
		<template #knowledge><KnowledgePanel /></template>
	</SettingsDialog>
</template>

<script setup>
import { computed, inject, watch } from "vue";
import SettingsDialog from "@flow/ui-core/components/SettingsDialog.vue";

import DocPanel from "./DocPanel.vue";
import GeneralPanel from "./GeneralPanel.vue";
import KnowledgePanel from "./KnowledgePanel.vue";
import ModelsPanel from "./ModelsPanel.vue";
import { SPECS } from "./specs.js";

const DESCRIPTIONS = {
	agents: "The agents you can chat with.",
	skills: "Instructions agents can use for specific tasks.",
	tools: "Actions agents can take.",
	triggers: "Run an agent when a document changes or on a schedule.",
	memories: "What agents have remembered.",
};
const ICONS = {
	general: "lucide-settings",
	agents: "lucide-bot",
	skills: "lucide-book-open",
	tools: "lucide-wrench",
	triggers: "lucide-workflow",
	models: "lucide-box",
	knowledge: "lucide-database",
	memories: "lucide-bookmark",
};

const page = inject("flowPage");
// models and the providers they come from share one tab of their own
const docKeys = ["agents", "skills", "tools", "triggers", "memories"];
const docSpecs = computed(() =>
	docKeys.map((key) => SPECS[key]).filter((spec) => page.can(spec.doctype, "read"))
);

// the dialog's tabs, grouped; a tab is offered only when the user may read its doctype
const groups = computed(() => {
	const tab = (id, label) => ({ id, label, icon: ICONS[id] });
	const allowed = new Set(docSpecs.value.map((spec) => spec.key));
	const docTab = (key) => (allowed.has(key) ? tab(key, SPECS[key].label) : null);
	return [
		{
			label: "Chat",
			// models are set up by those who may change them; everyone else picks one in the composer
			tabs: [tab("general", "General"), page.can("Flow Model", "write") ? tab("models", "Models") : null],
		},
		{ label: "Agents", tabs: ["agents", "skills", "tools", "triggers"].map(docTab) },
		{
			label: "Knowledge",
			tabs: [
				page.can("Flow Knowledge Base", "read") ? tab("knowledge", "Knowledge") : null,
				docTab("memories"),
			],
		},
	]
		.map((group) => ({ ...group, tabs: group.tabs.filter(Boolean) }))
		.filter((group) => group.tabs.length);
});

// the providers had a tab of their own; whatever still asks for it gets the one they share
watch(
	() => page.state.settingsTab,
	(tab) => tab === "providers" && (page.state.settingsTab = "models"),
	{ immediate: true }
);
</script>
