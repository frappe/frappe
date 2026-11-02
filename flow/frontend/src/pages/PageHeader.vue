<template>
	<header class="flex h-11 flex-none items-center gap-2 px-3">
		<!-- set apart from the page's icon, which would otherwise read as one more button -->
		<div v-if="noSidebar || !flow.state.sidebarOpen" class="flex items-center gap-2 md:mr-1.5">
			<!-- with no sidebar to show, the page leads back to the chat -->
			<button v-if="noSidebar" class="flow-icon-btn" title="Back to chat" @click="leavePage()">
				<span class="lucide-arrow-left size-4" aria-hidden="true" />
			</button>
			<button v-else class="flow-icon-btn" title="Show sidebar" @click="flow.setSidebarOpen(true)">
				<span class="lucide-panel-left size-4" aria-hidden="true" />
			</button>
			<button class="flow-icon-btn max-md:hidden" title="New chat" @click="newChat">
				<span class="lucide-plus size-4" aria-hidden="true" />
			</button>
		</div>
		<!-- the page's icon and name; a narrow frame's bar keeps the name alone, for the room its
		     actions leave -->
		<nav
			:class="{ 'ml-2': !noSidebar && flow.state.sidebarOpen }"
			class="flex min-w-0 items-center gap-2 text-base"
			aria-label="Breadcrumb"
		>
			<span :class="icon" class="size-4 flex-none text-ink-gray-5 max-md:hidden" aria-hidden="true" />
			<h1 class="min-w-0 truncate font-medium text-ink-gray-9">{{ title }}</h1>
		</nav>
		<span class="min-w-2 flex-1" />
		<div class="flex flex-none items-center gap-2 [&_button]:text-base">
			<slot name="actions" />
		</div>
	</header>
</template>

<script setup>
import { inject } from "vue";

// A page's bar, where a chat has its header: the way to the sidebar while it is hidden, where
// the page sits, and its actions at the end.
defineProps({
	icon: { type: String, required: true }, // a lucide-* class
	title: { type: String, required: true },
});
const flow = inject("flow");
const leavePage = inject("leavePage");
const noSidebar = inject("noSidebar");

// a new chat, in place of the one waiting behind the page, once the page lets go
async function newChat() {
	if (await leavePage()) flow.startNewChat();
}
</script>
