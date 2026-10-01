<template>
	<!-- clip, not hidden: a hidden root still scrolls when focus lands in the closed panel -->
	<div class="flex h-full min-h-0 overflow-clip bg-surface-base text-base text-ink-gray-8">
		<SessionSidebar :open="sidebarOpen" @close="store.setSidebarOpen(false)" />
		<main class="relative flex min-w-0 flex-1 flex-col bg-surface-base">
			<ChatHeader
				:sidebar-open="sidebarOpen"
				:workspace="false"
				@open-sidebar="store.setSidebarOpen(true)"
			/>
			<MessageList>
				<template #empty>
					<SetupState v-if="needsSetup" />
					<template v-else>
						<BrandMark :size="52" />
						<h2
							class="max-w-xs text-6xl font-normal leading-snug tracking-[-0.01em] text-ink-gray-9 sm:max-w-none"
						>
							What can I help you with?
						</h2>
					</template>
				</template>
			</MessageList>
			<Composer
				ref="composer"
				:commands="COMMANDS"
				:mentions="false"
				:images-only="false"
				:placeholder="placeholder"
				:modes="MODES"
				:disabled="needsSetup"
			>
				<template #toolbar="{ openPalette }">
					<AgentPicker @open="openPalette" />
					<span aria-hidden="true" class="flex-none text-xs text-ink-gray-3">/</span>
					<ModelButton @open="openPalette" />
				</template>
				<template #palette="{ view, close, back }">
					<AgentPalette v-if="view === 'agents'" @close="close" @back="back" />
				</template>
			</Composer>
		</main>
		<WorkspacePanel>
			<template #empty>
				<p class="text-xs text-ink-gray-4">A sub-agent's thread opens here.</p>
			</template>
		</WorkspacePanel>
		<Dialogs />
		<ToastProvider />
		<FlowSettings />
		<TranscriptDialog />
	</div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, provide, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { Dialogs, ToastProvider, toast, useColorScheme } from "frappe-ui";
import BrandMark from "@flow/ui-core/components/BrandMark.vue";
import ChatHeader from "@flow/ui-core/components/ChatHeader.vue";
import Composer from "@flow/ui-core/components/Composer.vue";
import MessageList from "@flow/ui-core/components/MessageList.vue";
import ModelButton from "@flow/ui-core/components/ModelButton.vue";
import SessionSidebar from "@flow/ui-core/components/SessionSidebar.vue";
import TranscriptDialog from "@flow/ui-core/components/TranscriptDialog.vue";
import WorkspacePanel from "@flow/ui-core/components/WorkspacePanel.vue";
import { installShortcuts } from "@flow/ui-core/shortcuts.js";
import { provideComposerHeight } from "@flow/ui-core/composerHeight.js";
import { createFlowStore } from "@flow/ui-core/store.js";

import { FrappeClient } from "../api/client.js";
import * as transport from "../api/frappe.js";
import { connectSocket } from "../api/socket.js";
import { createPage } from "../page.js";
import FlowSettings from "../settings/FlowSettings.vue";
import AgentPalette from "./AgentPalette.vue";
import AgentPicker from "./AgentPicker.vue";
import FeedbackBar from "./FeedbackBar.vue";
import SetupState from "./SetupState.vue";
import { presentTool } from "./toolMeta.js";

// the composer commands Flow serves, its own agent picker first; the rest need the
// daemon's file system or providers
const COMMANDS = [
	{ name: "agents", label: "Agent", icon: "bot", hint: "choose the agent", view: "agents" },
	"model",
	"thinking",
	"settings",
	"transcript",
	"new",
	"abort",
];
// the approval modes in Flow's terms: its tools act on documents, not files
const MODES = [
	{
		id: "ask",
		label: "Ask for approval",
		desc: "Pauses before a tool creates, changes or runs anything.",
	},
	{ id: "auto", label: "Auto-approve", desc: "Runs every tool without stopping to ask." },
];

const props = defineProps({ boot: { type: Object, required: true } });

// the store's model refresh is the boot call; the page asks for it when boot goes stale
const page = createPage(props.boot, { refresh: () => store.refreshModels() });
const socket = connectSocket(props.boot);
const client = new FrappeClient({
	socket,
	boot: props.boot,
	transport,
	hooks: {
		agent: () => page.state.agent,
		onBoot: page.onBoot,
		onSession: page.onSession,
		onRows: page.onRows,
	},
});
const store = createFlowStore(client, {
	requireCwd: false,
	storageKey: `flow.page.${props.boot.user?.name ?? "user"}`,
	presentTool,
	turnActions: FeedbackBar,
});
provide("flow", store);
provide("flowPage", page);
useColorScheme();
// the store keys a new chat's skills by folder; here they follow the chosen agent
watch(
	() => page.state.agent,
	() => void store.loadSkills({ force: true })
);

const sidebarOpen = computed(() => store.state.sidebarOpen);
// the composer asks in the name of the agent that answers
const placeholder = computed(() => {
	const name = store.state.session?.agent ?? page.state.agent;
	const title = page.state.boot.agents.find((agent) => agent.name === name)?.title ?? "Flow";
	return `Ask ${title}…`;
});
// no model or no agent: the empty state says so, and the composer waits
const needsSetup = computed(
	() => !page.state.boot.models?.length || !page.state.boot.agents?.length
);

// the composer floats over the list, which pads by its measured height
const composer = ref(null);
provideComposerHeight(composer);

watch(
	() => store.state.toast,
	(item) => {
		if (!item) return;
		if (item.kind === "error") toast.error(item.message);
		else toast.success(item.message);
	}
);

// the route names the open conversation, so links and reloads keep it
const route = useRoute();
const router = useRouter();
watch(
	() => store.state.sessionId,
	(id) => {
		const target = id ? `/s/${id}` : "/";
		if (route.path !== target) router.replace(target);
	}
);
watch(
	() => route.params.session,
	(id) => {
		if (id && id !== store.state.sessionId) store.openSession(id);
		else if (!id && store.state.sessionId) store.startNewChat();
	}
);
watch(
	() => store.state.session?.title,
	(title) => (document.title = title ? `${title} · Flow` : "Flow")
);

let uninstallShortcuts = null;
onMounted(async () => {
	uninstallShortcuts = installShortcuts(store);
	store.refreshModels();
	await store.refreshSessions();
	// the route watcher may have opened the URL's session while the list was loading
	const wanted = route.params.session ?? store.state.prefs.lastSession;
	if (wanted === store.state.sessionId) return;
	if (
		wanted &&
		(route.params.session ||
			store.state.sessions.some((session) => session.session_id === wanted))
	)
		store.openSession(wanted);
});
onBeforeUnmount(() => {
	uninstallShortcuts?.();
	store.detach();
	socket.disconnect();
});
</script>
