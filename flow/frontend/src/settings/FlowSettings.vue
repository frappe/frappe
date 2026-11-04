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
import { layout } from "@flow/ui-core/layout.js";

import { inPanel } from "../panel.js";
import DocPanel from "./DocPanel.vue";
import GeneralPanel from "./GeneralPanel.vue";
import KnowledgePanel from "./KnowledgePanel.vue";
import ModelsPanel from "./ModelsPanel.vue";
import { SPECS } from "./specs.js";

const DESCRIPTIONS = {
	agents: "Who answers, and what each agent can do.",
	skills: "Know-how agents can pick up for particular tasks.",
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
const flow = inject("flow");
const host = inject("flowHost", null);
// models and the services they come from share one tab of their own
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
		// models sit with what they answer in, not under a heading that repeats their name
		{
			label: "Chat",
			tabs: [tab("general", "General"), page.can("Flow Model", "read") ? tab("models", "Models") : null],
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

// the providers had a tab of their own; whatever still asks for it gets the one they share now
watch(
	() => page.state.settingsTab,
	(tab) => tab === "providers" && (page.state.settingsTab = "models"),
	{ immediate: true }
);

// in the launcher's panel, the dialog fills the window while it's open (a phone's page fills the
// panel already); the panel goes back once the dialog's 150ms exit has played
let restore = null;
watch(
	() => flow.state.settingsOpen && !layout.phone,
	(open) => {
		if (!inPanel) return;
		clearTimeout(restore);
		const tell = () => host?.settings(open);
		if (open) tell();
		else restore = setTimeout(tell, 150);
	}
);
</script>
