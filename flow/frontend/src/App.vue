<script setup>
import { onMounted, onUnmounted, ref } from "vue";
import PanelHeader from "./components/PanelHeader.vue";
import MessageList from "./components/MessageList.vue";
import Composer from "./components/Composer.vue";
import { useStore } from "./store";

const props = defineProps({
	onClose: { type: Function, default: null },
	onToggleFullscreen: { type: Function, default: null },
});
const { loadInitial, scrollTick } = useStore();

const panel = ref(null);
const composer = ref(null);
let observer = null;

// The composer floats over the message list, so the list pads its bottom by the
// composer's live height (--flow-composer-h) — a grown composer (attachments,
// multiline text) must never cover the last message.
onMounted(() => {
	loadInitial();
	observer = new ResizeObserver(([entry]) => {
		panel.value?.style.setProperty("--flow-composer-h", `${entry.target.offsetHeight}px`);
		scrollTick.value++;
	});
	observer.observe(composer.value.$el);
});
onUnmounted(() => observer?.disconnect());
</script>

<template>
	<div
		ref="panel"
		class="flow-panel relative flex h-full flex-col border-l border-outline-gray-2 bg-surface-white text-ink-gray-9"
	>
		<PanelHeader
			:on-toggle-fullscreen="props.onToggleFullscreen"
			@close="props.onClose && props.onClose()"
		/>
		<MessageList />
		<Composer ref="composer" />
	</div>
</template>
