<template>
	<!-- clip, not hidden: a hidden root still scrolls when focus lands in the closed panel.
	     The root is the sidebar's colour, so the chat stands on it as a raised panel -->
	<div class="flow-sidebar-surface flex h-full min-h-0 overflow-clip text-base text-ink-gray-8">
		<SessionSidebar
			:open="sidebarOpen"
			:chat-in-view="!pageKind"
			:before-switch="leavePage"
			@close="store.setSidebarOpen(false)"
		>
			<!-- a group under its own heading, spaced as the chats' heading is under it -->
			<template #nav>
				<h3
					v-if="pages.length"
					class="mt-[7px] flex h-8 items-center pl-2 text-xs font-medium text-ink-gray-5"
				>
					Build
				</h3>
				<SidebarItem
					v-for="item in pages"
					:key="item.key"
					:icon="item.icon"
					:route="`/${item.key}`"
					:active="pageKind === item.key"
					class="h-8 data-[state=active]:bg-surface-gray-3 data-[state=active]:shadow-none"
					@click="layout.narrow && store.setSidebarOpen(false)"
				>
					<span class="truncate text-xs font-medium text-ink-gray-8">{{
						SPECS[item.key].label
					}}</span>
				</SidebarItem>
			</template>
		</SessionSidebar>
		<div
			class="flex min-w-0 flex-1 overflow-clip bg-surface-base md:m-1 md:rounded-5 md:shadow-sm"
		>
			<RecordPage v-if="pageKind" :kind="pageKind" />
			<!-- hidden under a page, not taken away: the chat waits as it was, its box's draft and
			     files too, and inert, so nothing in it answers keys meanwhile -->
			<main
				v-show="!pageKind"
				:inert="pageKind ? true : null"
				class="relative flex min-w-0 flex-1 flex-col bg-surface-base"
			>
				<ChatHeader
					:sidebar-open="sidebarOpen"
					:workspace="false"
					:actions="chatActions"
					:crumb="agentCrumb"
					@open-sidebar="store.setSidebarOpen(true)"
				/>
				<MessageList :suggestions="!readOnly">
					<template #empty>
						<SetupState v-if="needsSetup" />
						<template v-else>
							<!-- a step smaller on a phone, and smaller still where the heading would run out of room -->
							<BrandMark
								:size="52"
								class="min-h-0 shrink max-sm:!h-10 max-sm:!w-10"
							/>
							<h2
								class="text-balance text-4xl font-normal leading-snug tracking-[-0.01em] text-ink-gray-9 sm:text-6xl"
							>
								What can I help you with?
							</h2>
						</template>
					</template>
				</MessageList>
				<Composer
					v-if="!readOnly && !needsSetup"
					ref="composer"
					:commands="COMMANDS"
					:mentions="false"
					:images-only="false"
					:placeholder="placeholder"
					:modes="MODES"
				>
					<template #start="{ insert }">
						<AgentPicker />
						<SkillPicker @pick="insert" />
					</template>
					<template #palette="{ view, query, close, back }">
						<AgentPalette
							v-if="view === 'agents'"
							:query="query"
							@close="close"
							@back="back"
						/>
					</template>
				</Composer>
				<p
					v-else-if="readOnly"
					class="absolute inset-x-0 bottom-0 px-5 pb-5 text-center text-xs text-ink-gray-5"
				>
					{{ readOnlyNote }}
				</p>
			</main>
			<WorkspacePanel v-if="!pageKind">
				<template #empty>
					<p class="text-xs text-ink-gray-4">A sub-agent's thread opens here.</p>
				</template>
			</WorkspacePanel>
		</div>
		<Dialogs />
		<!-- a narrow frame's toasts drop from the top, off the composer, as the harness's do -->
		<ToastProvider :position="layout.narrow ? 'top-center' : 'bottom-right'" />
		<FlowSettings />
		<TranscriptDialog />
		<ShareChat v-if="canShare" ref="share" />
	</div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, provide, ref, watch } from "vue";
import { isNavigationFailure, useRoute, useRouter } from "vue-router";
import { Dialogs, ToastProvider, toast, useColorScheme } from "frappe-ui";
import SidebarItem from "frappe-ui/src/components/Sidebar/SidebarItem.vue";
import BrandMark from "@flow/ui-core/components/BrandMark.vue";
import ChatHeader from "@flow/ui-core/components/ChatHeader.vue";
import Composer from "@flow/ui-core/components/Composer.vue";
import MessageList from "@flow/ui-core/components/MessageList.vue";
import SessionSidebar from "@flow/ui-core/components/SessionSidebar.vue";
import TranscriptDialog from "@flow/ui-core/components/TranscriptDialog.vue";
import WorkspacePanel from "@flow/ui-core/components/WorkspacePanel.vue";
import { installShortcuts } from "@flow/ui-core/shortcuts.js";
import { installFocusRings } from "@flow/ui-core/focusRings.js";
import { installViewport } from "@flow/ui-core/viewport.js";
import { provideComposerHeight } from "@flow/ui-core/composerHeight.js";
import { layout } from "@flow/ui-core/layout.js";
import { createFlowStore } from "@flow/ui-core/store.js";

import { FrappeClient } from "../api/client.js";
import * as transport from "../api/frappe.js";
import { connectSocket } from "../api/socket.js";
import { createPage } from "../page.js";
import RecordPage from "../pages/RecordPage.vue";
import { PAGES } from "../pages/pages.js";
import FlowSettings from "../settings/FlowSettings.vue";
import { SPECS } from "../settings/specs.js";
import AgentPalette from "./AgentPalette.vue";
import AgentPicker from "./AgentPicker.vue";
import FeedbackBar from "./FeedbackBar.vue";
import SetupState from "./SetupState.vue";
import ShareChat from "./ShareChat.vue";
import SkillPicker from "./SkillPicker.vue";
import { useAgent } from "./agent.js";
import { presentTool } from "./toolMeta.js";

// the composer commands Flow serves, its own agent picker first; the rest need the
// daemon's file system or providers
const COMMANDS = [
	{ name: "agents", label: "Agent", icon: "bot", hint: "Choose the agent", view: "agents" },
	"model",
	"thinking",
	"transcript",
	"new",
	"rewind",
	"compact",
	"abort",
	"settings",
];
// the approval modes in Flow's terms: its tools act on documents, not files
const MODES = [
	{ id: "ask", label: "Ask for approval", desc: "Asks before changing anything." },
	{ id: "auto", label: "Auto-approve", desc: "Runs everything without asking." },
];

const props = defineProps({ boot: { type: Object, required: true } });
// what the page and the store save, per user
const storageKey = `flow.page.${props.boot.user?.name ?? "user"}`;

// the store's model refresh is the boot call; the page asks for it when boot goes stale
const page = createPage(props.boot, {
	storageKey,
	refresh: () => store.refreshModels(),
	sync: (sid) => client.syncSession(sid),
	renamedModel: (from, to) => store.renamedModel(from, to),
	reloadSkills: () => store.loadSkills({ force: true }),
});
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
	storageKey,
	presentTool,
	turnActions: FeedbackBar,
	listedModel: true, // list_sessions names each chat's model in force
	onlyListedModels: true, // boot lists the models this user may use
});
provide("flow", store);
provide("flowPage", page);
useColorScheme();
// the store keys a new chat's skills by folder; here they follow the chosen agent
watch(
	() => page.state.agent,
	() => void store.loadSkills({ force: true })
);
// a new chat starts on its agent's model; one picked for it holds until the agent changes,
// and over a reload while the user may still use it
let onLoad = true;
watch(
	[
		() => !store.state.sessionId,
		() => page.state.agent,
		() => page.state.boot.agents.find((agent) => agent.name === page.state.agent)?.model,
	],
	([draft, , model]) => {
		const picked = store.state.prefs.lastModel;
		const kept = onLoad && page.state.boot.models.some((m) => m.name === picked);
		onLoad = false;
		if (draft && model && !kept) store.selectModel(model);
	},
	{ immediate: true }
);

const sidebarOpen = computed(() => store.state.sidebarOpen);
// the composer asks in the name of the agent that answers
const placeholder = computed(() => {
	const name = store.state.session?.agent ?? page.state.agent;
	const title = page.state.boot.agents.find((agent) => agent.name === name)?.title ?? "Flow";
	return `Ask ${title}…`;
});
// the header names a chat's agent where the harness names its folder
const { current: agent, title: agentTitle } = useAgent(store, page);
const agentCrumb = computed(() => (agent.value ? { icon: "bot", label: agentTitle.value } : null));
// someone else's chat is view-only: its tools would run as its owner
const readOnly = computed(() => Boolean(page.state.readOnly[store.state.sessionId]));
// only its owner shares a chat, once it has loaded and said who that is
const canShare = computed(() => {
	const owner = page.state.owner[store.state.sessionId]?.name;
	return Boolean(owner) && owner === page.state.boot.user?.name;
});
// the owner's chat menu leads with Share
const share = ref(null);
const chatActions = computed(() =>
	canShare.value
		? [{ label: "Share", icon: "lucide-share-2", onClick: () => share.value.show() }]
		: []
);
// a viewer learns whose chat it is
const readOnlyNote = computed(() => {
	const owner = page.state.owner[store.state.sessionId]?.full_name;
	return owner
		? `Only ${owner} can send messages in this chat.`
		: "Only the owner of this chat can send messages.";
});
// no model or no agent: the empty state says so, and there is no composer yet
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
// the pages beside the chats, each for whoever may read its records
const pages = computed(() => PAGES.filter((item) => page.can(SPECS[item.key].doctype, "read")));
const pageKind = computed(() =>
	pages.value.some((item) => item.key === route.params.kind) ? route.params.kind : null
);
watch(
	() => store.state.sessionId,
	(id) => {
		if (route.params.kind) return; // a page is left by a link of its own
		const target = id ? `/s/${id}` : "/";
		if (route.path !== target) router.replace(target);
	}
);
watch(
	() => route.params.session,
	(id) => {
		if (pageKind.value) return; // the chat waits behind a page as it was, its box and all
		if (id && id !== store.state.sessionId) store.openSession(id);
		else if (!id && store.state.sessionId) store.startNewChat();
	}
);

// a page the user may not read is the new chat
watch(
	() => route.params.kind && !pageKind.value,
	(refused) => refused && router.replace("/"),
	{ immediate: true }
);
// back from a page at a new chat's address, a chat that opened behind it (a first message's)
// takes its own
watch(pageKind, (kind, was) => {
	if (was && !kind && route.name === "new" && store.state.sessionId)
		router.replace(`/s/${store.state.sessionId}`);
});
// whatever changes the chat behind a page waits for this: back to that chat, through the page's
// guard (unsaved edits ask). False keeps the page, and the chat as it was
async function leavePage() {
	if (!pageKind.value) return true;
	const failure = await router.push(store.state.sessionId ? `/s/${store.state.sessionId}` : "/");
	return !isNavigationFailure(failure);
}
provide("leavePage", leavePage);

// the tab names the chat, or the page and its record as the page's bar does
watch(
	() => {
		if (!pageKind.value) return store.state.session?.title;
		const spec = SPECS[pageKind.value];
		const { record } = route.params;
		return !record ? spec.label : record === "new" ? `New ${spec.singular}` : record;
	},
	(title) => (document.title = title ? `${title} · Flow` : "Flow")
);

let uninstallShortcuts = null;
let uninstallFocusRings = null;
let uninstallViewport = null;
onMounted(async () => {
	// in the launcher's panel, the app around the page keeps the keyboard's shortcuts
	if (window.top === window) uninstallShortcuts = installShortcuts(store);
	uninstallFocusRings = installFocusRings();
	uninstallViewport = installViewport();
	store.refreshModels();
	await store.refreshSessions();
	// the route watcher, a click or a first message may have moved on while the list loaded,
	// and a page keeps its place
	if (store.state.sessionId || store.state.conversation.sending.length || route.params.kind)
		return;
	// an address asking for a new chat (?new=1, as the launcher's panel does after a close) gets one
	const wanted =
		route.params.session ?? (route.query.new ? null : store.state.prefs.lastSession);
	if (
		wanted &&
		(route.params.session ||
			store.state.sessions.some((session) => session.session_id === wanted))
	)
		store.openSession(wanted);
});
onBeforeUnmount(() => {
	uninstallShortcuts?.();
	uninstallFocusRings?.();
	uninstallViewport?.();
	store.detach();
	socket.disconnect();
});
</script>
