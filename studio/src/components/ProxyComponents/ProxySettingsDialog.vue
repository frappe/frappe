<template>
	<ProxyDialog class="mx-auto" :size="size ?? '4xl'" bare>
		<TabsRoot
			v-model="activeTab"
			orientation="vertical"
			activation-mode="manual"
			:unmount-on-hide="false"
			class="flex min-h-0 w-full flex-col overflow-hidden sm:h-[min(860px,calc(100vh-8rem))] sm:min-h-[560px] sm:flex-row"
		>
			<slot />
		</TabsRoot>
	</ProxyDialog>
</template>

<script setup lang="ts">
import { ref, watch } from "vue"
import { TabsRoot } from "reka-ui"
import ProxyDialog from "@/components/ProxyComponents/ProxyDialog.vue"

// StudioComponent binds all of SettingsDialog's props; only `tab` and `size` matter here.
// The modal/teleport/shortcut behaviour is intentionally dropped so the dialog shows inline.
const props = defineProps<{
	modelValue?: boolean
	tab?: string | number
	size?: string
	shortcut?: boolean
	unmountOnHide?: boolean
}>()

// Seed the active tab from `tab` (the block template defaults it to the first nav value)
// so a panel is visible on open; clicking a nav item updates it locally so tabs navigate.
const activeTab = ref(props.tab)
watch(
	() => props.tab,
	(value) => (activeTab.value = value),
)
</script>
