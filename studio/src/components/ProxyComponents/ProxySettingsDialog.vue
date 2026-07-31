<template>
	<!-- Editor stand-in for the teleported SettingsDialog. The real component composes
	     Dialog (bare, teleported modal) → TabsRoot, so it's invisible on the canvas; this
	     proxy mirrors that composition with ProxyDialog (which supplies the dialog chrome
	     and size → width handling) and renders the inner TabsRoot inline and always "open"
	     so the sidebar + panels are visible and editable in fragment mode. The child
	     sidebar/nav/panels inject their Tabs context (TabsList/TabsTrigger/TabsContent)
	     from this TabsRoot. -->
	<ProxyDialog class="mx-auto" :size="size ?? '4xl'" bare>
		<TabsRoot
			v-model="activeTab"
			orientation="vertical"
			activation-mode="manual"
			:unmount-on-hide="false"
			class="flex min-h-[480px] w-full flex-col sm:flex-row"
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
