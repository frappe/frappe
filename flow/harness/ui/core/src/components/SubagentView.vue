<template>
	<!-- the child's thread, drawn by the same list as the session's -->
	<MessageList v-if="thread" :conversation="thread" />
	<div v-else class="flex flex-1 items-center justify-center text-xs text-ink-gray-4">Starting…</div>
</template>

<script setup>
import { computed, inject, provide, ref } from "vue"

import MessageList from "./MessageList.vue"

const props = defineProps({ id: { type: String, required: true } })
const flow = inject("flow")
const thread = computed(() => flow.state.conversation.subagents[props.id] ?? null)
// no composer floats over the panel, so the list needs no room for one
provide("composerHeight", ref(0))
</script>
