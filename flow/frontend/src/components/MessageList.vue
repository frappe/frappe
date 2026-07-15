<script setup>
import { ref, watch } from "vue";
import UserMessage from "./UserMessage.vue";
import AssistantMessage from "./AssistantMessage.vue";
import EmptyState from "./EmptyState.vue";
import { FeatherIcon } from "@/lib/ui";
import { useStore } from "@/store";
import { __ } from "@/lib/translate";

const { messages, needsSetup, agents, models, scrollTick, forceScroll } = useStore();

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
	if (e && (stick || forceScroll.value)) {
		// Smooth for explicit actions (send / approval); instant while streaming
		// so it doesn't lag behind a fast token stream.
		e.scrollTo({ top: e.scrollHeight, behavior: forceScroll.value ? "smooth" : "auto" });
		stick = true;
	}
	forceScroll.value = false;
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
		class="flow-scrollbar flex flex-1 flex-col overflow-y-auto px-5 pt-4 pb-[calc(var(--flow-composer-h,104px)+24px)]"
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
				<template v-if="msg.role === 'user'">
					<UserMessage :content="msg.content" :attachments="msg.attachments" />
					<div
						v-if="msg.interrupted"
						class="flex items-center gap-1.5 text-[length:var(--text-sm)] text-ink-gray-5"
					>
						<FeatherIcon name="alert-circle" class="h-3.5 w-3.5 shrink-0" />
						{{ __("Response interrupted") }}
					</div>
				</template>
				<AssistantMessage v-else :message="msg" />
			</template>
		</div>
	</div>
</template>
