<script setup>
import { ref, watch } from "vue";
import UserMessage from "./UserMessage.vue";
import AssistantMessage from "./AssistantMessage.vue";
import EmptyState from "./EmptyState.vue";
import { useStore } from "@/store";

const { messages, needsSetup, agents, models, scrollTick } = useStore();

const el = ref(null);
let frame = 0;
let stick = true; // follow new content unless the user scrolled up

function onScroll() {
	const e = el.value;
	if (e) stick = e.scrollHeight - e.scrollTop - e.clientHeight < 80;
}

function scrollDown() {
	frame = 0;
	const e = el.value;
	if (e && stick) e.scrollTop = e.scrollHeight;
}

// Coalesce burst scroll requests (one per frame) so a fast token stream doesn't
// thrash layout.
watch(scrollTick, () => {
	if (!frame) frame = requestAnimationFrame(scrollDown);
});
</script>

<template>
	<div
		ref="el"
		class="flow-scrollbar flex flex-1 flex-col overflow-y-auto px-4 py-3"
		@scroll="onScroll"
	>
		<div class="mx-auto flex w-full max-w-3xl flex-1 flex-col gap-5">
			<EmptyState
				v-if="!messages.length"
				:setup="needsSetup"
				:has-models="models.length > 0"
				:has-agents="agents.length > 0"
			/>

			<template v-for="msg in messages" :key="msg.id">
				<UserMessage v-if="msg.role === 'user'" :content="msg.content" />
				<AssistantMessage v-else :message="msg" />
			</template>
		</div>
	</div>
</template>
