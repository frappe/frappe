<script setup>
import { onMounted } from "vue";
import PanelHeader from "./components/PanelHeader.vue";
import MessageList from "./components/MessageList.vue";
import Composer from "./components/Composer.vue";
import { useStore } from "./store";

const props = defineProps({ onClose: { type: Function, default: null } });
const { loadInitial } = useStore();

onMounted(loadInitial);
</script>

<template>
	<div
		class="flow-panel flex h-full flex-col border-l border-outline-gray-2 bg-surface-white text-ink-gray-9"
	>
		<PanelHeader @close="props.onClose && props.onClose()" />
		<MessageList />
		<Composer />
	</div>
</template>
