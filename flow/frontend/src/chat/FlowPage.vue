<template>
	<!-- clip, not hidden: a hidden root still scrolls when focus lands in the closed panel.
	     The root is the sidebar's colour, so on the /flow page the chat stands on it as a raised
	     panel; the launcher's panel keeps it flat at any size. The chat, its steps and the
	     composer all read at Desk's base size (14px), at every width -->
	<div
		ref="root"
		class="flow-sidebar-surface flex h-full min-h-0 overflow-clip text-base text-ink-gray-8 [--flow-chat-text:theme(fontSize.base)] [--flow-step-text:theme(fontSize.base)]"
	>
		<SessionSidebar
			v-if="!noSidebar"
			:open="sidebarOpen"
			:chat-in-view="!pageKind"
			:before-switch="leavePage"
			:apps="apps"
			:logout="logout"
			:user="page.state.boot.user"
			@close="store.setSidebarOpen(false)"
		>
			<template #brand><Badge label="Beta" size="sm" /></template>
		</SessionSidebar>
		<div
			class="flex min-w-0 flex-1 overflow-clip bg-surface-base"
			:class="inPanel ? '' : 'md:m-1 md:rounded-5 md:shadow-sm'"
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
					:history="noSidebar"
					:manage="!inPanel"
					:beside-navbar="panelHost"
					:app-menu="APP_MENU"
					:before-switch="leavePage"
					@open-sidebar="store.setSidebarOpen(true)"
				>
					<template v-if="inPanel" #end>
						<Button variant="ghost" icon="lucide-external-link" title="Open in new tab" @click="openInTab" />
						<Button variant="ghost" icon="lucide-x" title="Close" @click="closePanel" />
					</template>
				</ChatHeader>
				<MessageList :suggestions="!readOnly">
					<template #empty>
						<SetupState v-if="needsSetup" />
						<template v-else>
							<!-- no heading: the box's own "Ask Flow…" asks. The mark alone sits over it, a step
							     smaller in a narrow frame. It watches the pointer, reads what is typed, then
							     looks up when the draft rests; its word for that hangs under it, out of the
							     layout, so the box never moves -->
							<div class="relative mb-10 flex min-h-0 shrink flex-col items-center max-md:mb-8">
								<BrandMark
									line
									:size="32"
									:state="mood === 'idle' ? 'idle' : null"
									:look="MOOD[mood].look"
									class="min-h-0 shrink max-md:!h-7 max-md:!w-7"
								/>
								<p
									aria-live="polite"
									class="absolute top-full mt-2.5 whitespace-nowrap text-sm text-ink-gray-5 transition-opacity duration-300"
									:class="MOOD[mood].note ? 'opacity-100' : 'opacity-0'"
								>
									{{ MOOD[mood].note || MOOD.ready.note }}
								</p>
							</div>
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
					:plus-items="plusItems"
				>
					<!-- the page beside the panel, which the chat can read; dismissed, the chat leaves
					     that page alone until another opens -->
					<template v-if="crumb" #above>
						<div class="mb-1.5 flex min-w-0 items-center gap-1 px-3 text-sm text-ink-gray-5">
							<span class="lucide-app-window size-3.5 flex-none" aria-hidden="true" />
							<span class="truncate" :class="crumb.label ? '' : 'text-ink-gray-7'">{{ crumb.parent }}</span>
							<template v-if="crumb.label">
								<span class="flex-none text-ink-gray-4" aria-hidden="true">/</span>
								<span class="truncate text-ink-gray-7">{{ crumb.label }}</span>
							</template>
							<button
								class="ml-0.5 grid size-4 flex-none place-items-center rounded-4 text-ink-gray-4 hover:bg-surface-gray-2 hover:text-ink-gray-8"
								title="Stop working on this page"
								aria-label="Stop working on this page"
								@click="leftPage = crumb.key"
							>
								<span class="lucide-x size-3" aria-hidden="true" />
							</button>
						</div>
					</template>
					<template #below="{ starting }">
						<p v-if="starting" class="mt-2 px-3 text-center text-sm text-ink-gray-5">
							Flow is in beta and can make mistakes. Check what it shows you before you approve.
						</p>
					</template>
					<template #tools="{ insert, starting }">
						<AgentPicker v-if="starting" />
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
					class="absolute inset-x-0 bottom-0 px-5 pb-5 text-center text-sm text-ink-gray-5"
				>
					{{ readOnlyNote }}
				</p>
			</main>
			<WorkspacePanel v-if="!pageKind">
				<template #empty>
					<p class="text-sm text-ink-gray-4">A sub-agent's thread opens here.</p>
				</template>
			</WorkspacePanel>
		</div>
		<Dialogs />
		<!-- a narrow frame's toasts drop from the top, off the composer, as the harness's do, and
		     below the header, off its buttons -->
		<ToastProvider
			:position="layout.narrow ? 'top-center' : 'bottom-right'"
			:offset="toastOffset"
			:mobile-offset="toastOffset"
		/>
		<FlowSettings />
		<TranscriptDialog />
		<ShareChat v-if="canShare" ref="share" />
	</div>
</template>

<script setup>
import { computed, inject, onBeforeUnmount, onMounted, provide, ref, watch } from "vue";
import { isNavigationFailure, useRoute, useRouter } from "vue-router";
import { Badge, Button, Dialogs, ToastProvider, toast, useColorScheme } from "frappe-ui";
import { afterMenu, checked } from "@flow/ui-core/menu.js";
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
import { layout, measureLayoutBy } from "@flow/ui-core/layout.js";
import { createFlowStore } from "@flow/ui-core/store.js";

import { FrappeClient } from "../api/client.js";
import * as transport from "../api/frappe.js";
import { connectSocket } from "../api/socket.js";
import { createPage } from "../page.js";
import { inPanel, panelHost } from "../panel.js";
import RecordPage from "../pages/RecordPage.vue";
import { FORMS } from "../pages/pages.js";
import FlowSettings from "../settings/FlowSettings.vue";
import { SPECS } from "../settings/specs.js";
import AgentPalette from "./AgentPalette.vue";
import AgentPicker from "./AgentPicker.vue";
import FeedbackBar from "./FeedbackBar.vue";
import SetupState from "./SetupState.vue";
import ShareChat from "./ShareChat.vue";
import SkillPicker from "./SkillPicker.vue";
import { cameFrom, handOffPage, useDeskPage } from "./deskPage.js";
import { readScreen } from "./screen.js";
import { presentTool } from "./toolMeta.js";

// the composer commands Flow serves, its own agent picker first; the rest need the
// daemon's file system or providers
const COMMANDS = [
	{ name: "agents", label: "Agent", icon: "lucide-bot", hint: "Choose the agent", view: "agents" },
	"model",
	"thinking",
	"transcript",
	"new",
	"rewind",
	"compact",
	"abort",
	"settings",
];
// the way back to the rest of the site, in the floating sidebar's menu; the sidebar's own menu
// lists Desk under Apps
const APP_MENU = [
	{ label: "Go to Desk", icon: "lucide-external-link", onClick: () => (window.location.href = "/app") },
];
// a started chat's + menu nests the skills the full box lists from its button: a pick starts the
// draft with it, and with none yet, the way to a new one
// the agent a new chat will start with, ticked in the + menu's Agent list
const agentNow = computed(() => page.state.agent ?? page.state.boot.default_agent);
const plusItems = computed(() => {
	const skills = (store.state.skills ?? []).map((skill) => ({
		label: skill.name,
		onClick: ({ insert }) => insert(`/skill:${skill.name} `),
	}));
	const canAdd = page.can("Flow Skill", "create");
	const add = { label: "Add a skill", icon: "lucide-plus", onClick: afterMenu(() => (page.createRecord("skills"), store.setSettingsOpen(true))) };
	const items = [];
	// a new chat's agent, for a box too narrow for its own button (a started chat keeps its agent)
	if (!store.state.sessionId && page.state.boot.agents.length > 1)
		items.push({
			label: "Agent",
			icon: "lucide-brain-cog",
			submenu: page.state.boot.agents.map((agent) =>
				checked({ label: agent.title, onClick: () => (page.state.agent = agent.name) }, agent.name === agentNow.value)
			),
		});
	if (skills.length || canAdd)
		items.push({ label: "Skills", icon: "lucide-book-open", submenu: skills.length ? skills : [add] });
	return items;
});
// the approval modes in Flow's terms: its tools act on documents, not files
const MODES = [
	{ id: "auto", label: "Auto", desc: "A helper model handles approvals." },
	{ id: "ask", label: "Ask for approval", desc: "Asks before changing anything." },
	{ id: "auto_approve", label: "Auto-approve", desc: "Runs everything without asking." },
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
// in the launcher's panel the window's history is the page's around it
provide("flowBesidePage", inPanel);
// the Desk page beside the panel, or in a tab of its own the page it was opened from, named over
// the box; its × leaves that page out of the chat
const deskPage = inPanel ? useDeskPage() : ref(cameFrom());
const leftPage = ref(null);
const crumb = computed(() => (deskPage.value?.key === leftPage.value ? null : deskPage.value));

// the agent's read_screen: the panel reads the page beside it and answers for the chat it shows. A
// tab of its own has no page; it answers late, so a panel on the same chat is heard first
const STANDALONE_DELAY = 1500;
socket.on("flow:read_screen", async (message) => {
	if (!message?.token || message.session !== store.state.sessionId) return;
	const answer = { session: message.session, token: message.token };
	if (!inPanel) {
		await new Promise((resolve) => setTimeout(resolve, STANDALONE_DELAY));
		// the page it came from can't be read from here, but its record can
		if (crumb.value)
			answer.screen = {
				url: crumb.value.url,
				record: crumb.value.record ?? undefined,
				note: "Flow is open in a tab of its own; this is the page the user opened it from. Its text can't be read from here, so read the record itself.",
			};
		else answer.error = "Flow is open in a tab of its own, with no page beside it.";
	} else if (!crumb.value && deskPage.value) {
		answer.error = "The user took the page beside the chat out of it. Ask them what they mean.";
	} else {
		try {
			answer.screen = readScreen(window, root.value?.getRootNode().host);
		} catch (error) {
			answer.error = `The page beside the chat could not be read: ${error?.message ?? error}`;
		}
	}
	try {
		await transport.call("frappe.flow.api.screen_result", answer);
	} catch {
		// another panel on the chat answered first, or the call stopped waiting
	}
});
// the page around the panel owns the theme, which the island follows
if (!inPanel) useColorScheme();
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

// the launcher's panel, and a narrow frame worked by a mouse, have no sidebar: the chat's menu
// lists the chats, and a narrow tab's gear leads to settings, which the panel leaves to Desk and
// the /flow tab. A phone keeps the sidebar as a drawer
const noSidebar = computed(() => !layout.phone && (layout.narrow || inPanel));
provide("noSidebar", noSidebar);
const sidebarOpen = computed(() => !noSidebar.value && store.state.sidebarOpen);
// the sidebar menu's way to Desk and the other apps, asked for once a sidebar shows
const apps = ref([]);
watch(
	noSidebar,
	async (none) => {
		if (none || apps.value.length) return;
		const installed = await transport.call("frappe.apps.get_apps").catch(() => []);
		apps.value = [{ title: "Desk", route: "/desk", logo: "/assets/frappe/images/frappe-framework-logo.svg" }, ...installed];
	},
	{ immediate: true }
);
async function logout() {
	await transport.call("logout");
	window.location.assign("/login");
}
// the composer asks in the name of the agent that answers
const placeholder = computed(() => {
	const name = store.state.session?.agent ?? page.state.agent;
	const title = page.state.boot.agents.find((agent) => agent.name === name)?.title ?? "Flow";
	return `Ask ${title}…`;
});
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

// the launcher listens for the header's ×; a new tab takes the chat over from the panel
const host = inject("flowHost", null);
const closePanel = () => host?.close();
function openInTab() {
	if (crumb.value) handOffPage(crumb.value);
	window.open(`/flow${route.fullPath}`, "_blank", "noopener");
	closePanel();
}

const toastOffset = computed(() => (layout.narrow ? { top: 56 } : undefined));

// the composer floats over the list, which pads by its measured height
const composer = ref(null);
provideComposerHeight(composer);
// the new chat's mark, by the draft: at rest it watches the pointer, it reads while keys go,
// and a draft that rests a moment has it look up, ready. A "/" opens commands, not a message
const MOOD = {
	idle: { look: "pointer", note: "" },
	reading: { look: "down", note: "Reading…" },
	ready: { look: "up", note: "Ready when you are" },
};
const READ_PAUSE = 900; // ms of no typing before a draft rests
const typing = ref(false);
let typingPause = 0;
const draft = computed(() => composer.value?.text ?? "");
watch(draft, (text) => {
	clearTimeout(typingPause);
	typing.value = Boolean(text.trim());
	if (typing.value) typingPause = setTimeout(() => (typing.value = false), READ_PAUSE);
});
const mood = computed(() => {
	const text = draft.value.trim();
	if (!text || text.startsWith("/")) return "idle";
	return typing.value ? "reading" : "ready";
});
onBeforeUnmount(() => clearTimeout(typingPause));

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
// a setup form's record in the chat's place, for whoever may read its records
const forms = computed(() => FORMS.filter((item) => page.can(SPECS[item.key].doctype, "read")));
const pageKind = computed(() => {
	const { kind } = route.params;
	return forms.value.some((item) => item.key === kind) ? kind : null;
});
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
		// in the panel, a route the user didn't pick: the chat it last showed, or Back to one,
		// either of which may since be gone
		if (id && id !== store.state.sessionId) store.openSession(id, { quiet: inPanel });
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
// a page's floating sidebar offers the app menu's items as the sidebar does
provide("appMenu", APP_MENU);

// the tab names the chat, or the page and its record as the page's bar does
watch(
	() => {
		if (!pageKind.value) return store.state.session?.title;
		const { record } = route.params;
		return record === "new" ? `New ${SPECS[pageKind.value].singular}` : record;
	},
	(title) => {
		if (!inPanel) document.title = title ? `${title} · Flow` : "Flow";
	}
);

let uninstallShortcuts = null;
let uninstallFocusRings = null;
let uninstallViewport = null;
let unmeasure = null;
const root = ref(null);
onMounted(async () => {
	// an island lays out by its own box, which a panel narrows; the page's width says nothing
	unmeasure = measureLayoutBy(root.value);
	if (!inPanel) uninstallShortcuts = installShortcuts(store);
	uninstallFocusRings = installFocusRings(
		...[root.value, root.value.getRootNode().host].filter(Boolean)
	);
	// the page around the panel owns the window's viewport
	if (!inPanel) uninstallViewport = installViewport();
	store.refreshModels();
	await store.refreshSessions();
	// the route watcher, a click or a first message may have moved on while the list loaded,
	// and a page keeps its place
	if (store.state.sessionId || store.state.conversation.sending.length || route.params.kind)
		return;
	// an address asking for a new chat (?new=1) gets one
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
	unmeasure?.();
	store.detach();
	socket.disconnect();
});
</script>
