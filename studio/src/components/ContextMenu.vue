<!-- reka-ui based context menu (see Builder's ContextMenu). A zero-size fixed anchor at the
     cursor lets reka position + collision-handle the menu while we keep imperative control. -->
<template>
	<DropdownMenuRoot v-model:open="open" :modal="false">
		<DropdownMenuTrigger as-child>
			<span class="fixed size-0" :style="{ top: posY + 'px', left: posX + 'px' }" />
		</DropdownMenuTrigger>
		<DropdownMenuPortal>
			<DropdownMenuContent
				class="z-50 min-w-[150px] rounded-lg bg-surface-base p-1 text-sm shadow-2xl"
				:side-offset="0"
				align="start"
				avoid-collisions
			>
				<template v-for="(option, index) in options" :key="index">
					<!-- option with a nested submenu (Add Component) -->
					<DropdownMenuSub v-if="option.submenu && (!option.condition || option.condition())">
						<DropdownMenuSubTrigger
							class="flex cursor-pointer items-center justify-between gap-6 rounded px-3 py-1.5 text-ink-gray-8 outline-none data-[highlighted]:bg-surface-gray-3 data-[state=open]:bg-surface-gray-3"
						>
							{{ option.label }}
							<LucideChevronRight class="size-4 shrink-0 text-ink-gray-5" />
						</DropdownMenuSubTrigger>
						<DropdownMenuPortal>
							<DropdownMenuSubContent
								class="z-50 flex w-max min-w-[200px] flex-col rounded-lg bg-surface-base p-1 text-sm shadow-2xl"
								:side-offset="4"
								:align-offset="-4"
								avoid-collisions
								@open-auto-focus="onSubContentOpen"
							>
								<div class="js-submenu-search p-1" @keydown.stop @mousedown.stop @click.stop>
									<TextInput
										v-model="submenuSearch"
										size="sm"
										placeholder="Search components"
										class="[&_input]:text-sm"
									/>
								</div>
								<div class="max-h-80 overflow-y-auto">
									<template v-for="(group, groupIndex) in filterGroups(option.submenu)" :key="groupIndex">
										<DropdownMenuSeparator v-if="groupIndex > 0" class="mx-2 my-1 h-px bg-surface-gray-3" />
										<DropdownMenuGroup>
											<DropdownMenuLabel
												v-if="group.label"
												class="px-3 pb-1 pt-1.5 text-xs font-medium text-ink-gray-5"
											>
												{{ group.label }}
											</DropdownMenuLabel>
											<DropdownMenuItem
												v-for="(child, childIndex) in group.options"
												:key="childIndex"
												class="flex cursor-pointer items-center gap-2 rounded px-3 py-1.5 text-ink-gray-8 outline-none data-[highlighted]:bg-surface-gray-3"
												@select="child.action && handleClick(child.action)"
											>
												<component
													:is="child.icon"
													v-if="child.icon"
													class="size-4 shrink-0 text-ink-gray-6"
												/>
												<span class="truncate">{{ child.label }}</span>
											</DropdownMenuItem>
										</DropdownMenuGroup>
									</template>
									<div v-if="!filterGroups(option.submenu).length" class="px-3 py-1.5 text-ink-gray-4">
										No components found
									</div>
								</div>
							</DropdownMenuSubContent>
						</DropdownMenuPortal>
					</DropdownMenuSub>

					<!-- standard action option -->
					<DropdownMenuItem
						v-else-if="!option.submenu && (!option.condition || option.condition())"
						class="cursor-pointer rounded px-3 py-1.5 text-ink-gray-8 outline-none data-[disabled]:cursor-default data-[highlighted]:bg-surface-gray-3 data-[disabled]:text-ink-gray-3"
						:disabled="option.disabled && option.disabled()"
						@select="option.action && handleClick(option.action)"
					>
						{{ option.label }}
					</DropdownMenuItem>
				</template>
			</DropdownMenuContent>
		</DropdownMenuPortal>
	</DropdownMenuRoot>
</template>

<script setup lang="ts">
import {
	DropdownMenuRoot,
	DropdownMenuTrigger,
	DropdownMenuPortal,
	DropdownMenuContent,
	DropdownMenuItem,
	DropdownMenuSub,
	DropdownMenuSubTrigger,
	DropdownMenuSubContent,
	DropdownMenuSeparator,
	DropdownMenuGroup,
	DropdownMenuLabel,
} from "reka-ui"
import { TextInput } from "frappe-ui"
import { ref, nextTick, onMounted, watch } from "vue"
import type { ContextMenuOption, ContextMenuGroup } from "@/types"
import LucideChevronRight from "~icons/lucide/chevron-right"

const props = defineProps<{
	posX: number
	posY: number
	options: ContextMenuOption[]
}>()

const emit = defineEmits<{
	select: [action: CallableFunction]
	close: []
}>()

// open on mount (once the anchor exists) so reka positions against it; closing bubbles up as `close`
const open = ref(false)
onMounted(() => (open.value = true))
watch(open, (value) => {
	if (!value) emit("close")
})

const submenuSearch = ref("")

const filterGroups = (groups: ContextMenuGroup[]): ContextMenuGroup[] => {
	const query = submenuSearch.value.toLowerCase().trim()
	if (!query) return groups
	return groups
		.map((group) => ({
			...group,
			options: group.options.filter((o) => o.label.toLowerCase().includes(query)),
		}))
		.filter((group) => group.options.length)
}

// focus the search box instead of the first item so typing filters right away
const onSubContentOpen = (event: Event) => {
	event.preventDefault()
	submenuSearch.value = ""
	nextTick(() => {
		document.querySelector<HTMLInputElement>(".js-submenu-search input")?.focus()
	})
}

const handleClick = (action: CallableFunction) => {
	emit("select", action)
}
</script>
