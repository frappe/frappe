<template>
	<!-- Associates its content with a channel value shows only while active, 
		feeds its label to the switcher, and relays the
		 content's draft preview / focus (useComposerSurface) up to the window. -->
	<div v-show="isActive" class="flex h-full min-h-0 flex-1 flex-col">
		<slot />
	</div>
</template>

<script setup lang="ts">
import { computed, onUnmounted, reactive } from "vue";
import {
	injectComposer,
	provideChannelSurfaceSetter,
	type ChannelSurface,
} from "./composerContext";

const props = defineProps<{
	/** Identity — what `v-model:channel` on <Composer> takes. */
	value: string;
	/** Tab text; defaults to the capitalized value. */
	label?: string;
}>();

const composer = injectComposer();

const entry = reactive({
	value: props.value,
	label: computed(
		() => props.label || props.value.charAt(0).toUpperCase() + props.value.slice(1)
	),
	surface: null as ChannelSurface | null,
});

if (composer) {
	composer.register(entry);
	onUnmounted(() => composer.unregister(entry.value));
}

provideChannelSurfaceSetter((surface) => (entry.surface = surface));

const isActive = computed(() => !composer || composer.channel.value === props.value);
</script>
