<script setup>
import BrandMark from "./BrandMark.vue";
import SessionsMenu from "./SessionsMenu.vue";
import { Button, FeatherIcon } from "@/lib/ui";
import { useStore } from "@/store";
import { __ } from "@/lib/translate";

const props = defineProps({ onToggleFullscreen: { type: Function, default: null } });
const emit = defineEmits(["close"]);
const { recentSessions, switchSession, newChat, fullscreen } = useStore();
</script>

<template>
	<header class="flex items-center gap-1.5 border-b border-outline-gray-1 px-3 py-2">
		<BrandMark :size="18" />
		<span class="text-sm font-medium text-ink-gray-9">{{ __("Flow") }}</span>
		<span class="flex-1"></span>

		<SessionsMenu :sessions="recentSessions" @select="switchSession" />

		<Button variant="ghost" :title="__('New chat')" @click="newChat">
			<template #icon
				><FeatherIcon name="plus" :stroke-width="2" class="h-3.5 w-3.5"
			/></template>
		</Button>
		<Button
			variant="ghost"
			:title="fullscreen ? __('Exit full screen') : __('Full screen')"
			@click="props.onToggleFullscreen && props.onToggleFullscreen()"
		>
			<template #icon
				><FeatherIcon
					:name="fullscreen ? 'minimize' : 'maximize'"
					:stroke-width="2"
					class="h-3.5 w-3.5"
			/></template>
		</Button>
		<Button variant="ghost" :title="__('Close (Ctrl+I)')" @click="emit('close')">
			<template #icon
				><FeatherIcon name="x" :stroke-width="2" class="h-3.5 w-3.5"
			/></template>
		</Button>
	</header>
</template>
