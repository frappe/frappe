<!-- Extracted from Builder -->
<template>
	<Menu
		class="dark:bg-zinc-900 fixed z-50 h-fit w-fit min-w-[120px] rounded-lg bg-surface-base p-1 shadow-xl"
		:style="{ top: y + 'px', left: x + 'px' }"
		ref="menu"
	>
		<MenuItems static class="text-sm">
			<template v-for="(option, index) in options" :key="index">
				<!-- option with a nested submenu (expands on hover) -->
				<div
					v-if="option.submenu"
					v-show="!option.condition || option.condition()"
					class="relative"
					@mouseenter="onSubmenuEnter(index)"
					@mouseleave="openSubmenu = null"
				>
					<div
						class="dark:text-zinc-50 flex cursor-pointer items-center justify-between gap-4 rounded-md px-3 py-1 text-ink-gray-8"
						:class="openSubmenu === index ? 'dark:bg-zinc-700 bg-surface-gray-3' : ''"
					>
						{{ option.label }}
						<LucideChevronRight class="h-3 w-3 shrink-0" />
					</div>
					<div
						v-if="openSubmenu === index"
						class="dark:bg-zinc-900 absolute left-full top-0 z-50 flex max-h-[70vh] w-max min-w-[180px] flex-col rounded-lg bg-surface-base p-1 shadow-xl"
					>
						<div class="js-submenu-search p-1" @mousedown.stop @click.stop>
							<TextInput v-model="submenuSearch" size="sm" placeholder="Search components" @keydown.stop />
						</div>
						<div class="overflow-y-auto">
							<template v-for="(group, groupIndex) in filteredSubmenu" :key="groupIndex">
								<div v-if="group.label" class="px-3 pb-0.5 pt-1 text-xs font-medium text-ink-gray-5">
									{{ group.label }}
								</div>
								<div
									v-for="(child, childIndex) in group.options"
									:key="childIndex"
									class="dark:text-zinc-50 flex cursor-pointer items-center gap-2 rounded-md px-3 py-1 text-ink-gray-8 hover:bg-surface-gray-3"
									@click.prevent.stop="child.action && handleClick(child.action)"
								>
									<component :is="child.icon" v-if="child.icon" class="h-4 w-4 shrink-0 text-ink-gray-6" />
									<span class="truncate">{{ child.label }}</span>
								</div>
							</template>
							<div v-if="!filteredSubmenu.length" class="px-3 py-1 text-sm text-ink-gray-4">
								No components found
							</div>
						</div>
					</div>
				</div>

				<!-- standard action option -->
				<MenuItem
					v-else
					v-slot="{ active, disabled }"
					class="dark:text-zinc-50 block cursor-pointer rounded-md px-3 py-1"
					:disabled="option.disabled && option.disabled()"
					v-show="!option.condition || option.condition()"
				>
					<div
						@click.prevent.stop="
							(!option.condition || option.condition()) && option.action && handleClick(option.action)
						"
						:class="{
							'text-ink-gray-8': !disabled,
							'dark:bg-zinc-700 bg-surface-gray-3': active,
							'dark:text-zinc-500 text-ink-gray-3': disabled,
						}"
					>
						{{ option.label }}
					</div>
				</MenuItem>
			</template>
		</MenuItems>
	</Menu>
</template>

<script setup lang="ts">
import { Menu, MenuItem, MenuItems } from "@headlessui/vue"
import { FeatherIcon, TextInput } from "frappe-ui"
import { computed, ref, nextTick, watch } from "vue"
import type { ContextMenuOption } from "@/types"
import LucideChevronRight from "~icons/lucide/chevron-right"

const menu = ref(null) as unknown as typeof Menu
const openSubmenu = ref<number | null>(null)
const submenuSearch = ref("")

const props = defineProps<{
	posX: number
	posY: number
	options: ContextMenuOption[]
}>()

const onSubmenuEnter = (index: number) => {
	openSubmenu.value = index
	submenuSearch.value = ""
}

// focus the search box when a submenu opens so typing filters right away
watch(openSubmenu, (index) => {
	if (index === null) return
	nextTick(() => {
		menu.value?.$el?.querySelector<HTMLInputElement>(".js-submenu-search input")?.focus()
	})
})

const filteredSubmenu = computed(() => {
	const submenu = openSubmenu.value === null ? null : props.options[openSubmenu.value]?.submenu
	if (!submenu) return []
	const query = submenuSearch.value.toLowerCase().trim()
	if (!query) return submenu
	return submenu
		.map((group) => ({
			...group,
			options: group.options.filter((option) => option.label.toLowerCase().includes(query)),
		}))
		.filter((group) => group.options.length)
})

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
