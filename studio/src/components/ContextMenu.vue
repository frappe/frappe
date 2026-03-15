<!-- Extracted from Builder -->
<template>
	<Menu
		class="dark:bg-zinc-900 fixed z-50 h-fit w-fit min-w-[120px] rounded-lg bg-white p-1 shadow-xl"
		:style="{ top: y + 'px', left: x + 'px' }"
		ref="menu"
	>
		<MenuItems static class="text-sm">
			<MenuItem
				v-slot="{ active, disabled }"
				class="dark:text-zinc-50 block cursor-pointer rounded-md px-3 py-1"
				v-for="(option, index) in options"
				:disabled="option.disabled && option.disabled()"
				v-show="!option.condition || option.condition()"
			>
				<div
					@click.prevent.stop="(!option.condition || option.condition()) && handleClick(option.action)"
					:class="{
						'text-gray-900': !disabled,
						'dark:bg-zinc-700 bg-gray-200': active,
						'dark:text-zinc-500 text-gray-400': disabled,
					}"
				>
					{{ option.label }}
				</div>
			</MenuItem>
		</MenuItems>
	</Menu>
</template>

<script setup lang="ts">
import { Menu, MenuItem, MenuItems } from "@headlessui/vue"
import { computed, ref } from "vue"
import type { ContextMenuOption } from "@/types"

const menu = ref(null) as unknown as typeof Menu

const props = defineProps<{
	posX: number
	posY: number
	options: ContextMenuOption[]
}>()

const x = computed(() => {
	const menuWidth = menu.value?.$el.clientWidth
	const windowWidth = window.innerWidth
	const diff = windowWidth - (props.posX + menuWidth)
	if (diff < 0) {
		return props.posX + diff - 10
	}
	return props.posX
})

const y = computed(() => {
	const menuHeight = menu.value?.$el.clientHeight
	const windowHeight = window.innerHeight
	const diff = windowHeight - (props.posY + menuHeight)
	if (diff < 0) {
		return props.posY + diff - 10
	}
	return props.posY
})

const emit = defineEmits({
	select: (action: CallableFunction) => action,
})

const handleClick = (action: CallableFunction) => {
	emit("select", action)
}
</script>
