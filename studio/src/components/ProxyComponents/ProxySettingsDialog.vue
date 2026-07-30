<template>
	<!-- Editor stand-in for the teleported SettingsDialog. The real component renders
	     through frappe-ui's Dialog (teleported modal) so it's invisible on the canvas;
	     this proxy renders the dialog's inner TabsRoot inline and always "open" so the
	     sidebar + panels are visible and editable in fragment mode. It mirrors
	     SettingsDialog.vue's inner structure — the child sidebar/nav/panels inject their
	     Tabs context (TabsList/TabsTrigger/TabsContent) from this TabsRoot. -->
	<TabsRoot
		v-model="activeTab"
		orientation="vertical"
		activation-mode="manual"
		:unmount-on-hide="false"
		class="bg-surface-white mx-auto flex min-h-[480px] w-full max-w-4xl flex-col overflow-hidden rounded-xl border border-outline-gray-2 shadow-xl sm:flex-row"
	>
		<slot />
	</TabsRoot>
</template>

<script setup lang="ts">
import { ref, watch } from "vue"
import { TabsRoot } from "reka-ui"

// StudioComponent binds all of SettingsDialog's props; only `tab` matters here. The
// modal/teleport/shortcut behaviour is intentionally dropped so the dialog shows inline.
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
