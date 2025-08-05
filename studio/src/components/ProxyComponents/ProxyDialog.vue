<template>
	<div
		class="dialog-content inline-block w-full transform overflow-hidden rounded-xl bg-surface-modal text-left align-middle shadow-xl"
		:class="{
			'max-w-7xl': options.size === '7xl',
			'max-w-6xl': options.size === '6xl',
			'max-w-5xl': options.size === '5xl',
			'max-w-4xl': options.size === '4xl',
			'max-w-3xl': options.size === '3xl',
			'max-w-2xl': options.size === '2xl',
			'max-w-xl': options.size === 'xl',
			'max-w-lg': options.size === 'lg' || !options.size,
			'max-w-md': options.size === 'md',
			'max-w-sm': options.size === 'sm',
			'max-w-xs': options.size === 'xs',
		}"
	>
		<slot name="body">
			<slot name="body-main">
				<div class="bg-surface-modal px-4 pb-6 pt-5 sm:px-6">
					<div class="flex">
						<div class="w-full flex-1">
							<slot name="body-header">
								<div class="mb-6 flex items-center justify-between">
									<div class="flex items-center space-x-2">
										<div
											v-if="icon"
											class="flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-full"
											:class="dialogIconBgClasses"
										>
											<FeatherIcon
												:name="icon.name"
												class="h-4 w-4"
												:class="dialogIconClasses"
												aria-hidden="true"
											/>
										</div>
										<header>
											<slot name="body-title">
												<h3 class="text-2xl font-semibold leading-6 text-ink-gray-9">
													{{ options.title || "Untitled" }}
												</h3>
											</slot>
										</header>
									</div>
									<Button variant="ghost" @click="close">
										<template #icon>
											<LucideX class="h-4 w-4 text-ink-gray-9" />
										</template>
									</Button>
								</div>
							</slot>

							<slot name="body-content">
								<p class="text-p-base text-ink-gray-7" v-if="options.message">
									{{ options.message }}
								</p>
							</slot>
						</div>
					</div>
				</div>
			</slot>
			<div class="px-4 pb-7 pt-4 sm:px-6" v-if="actions.length || $slots.actions">
				<slot name="actions" v-bind="{ close }">
					<div class="space-y-2">
						<Button class="w-full" v-for="action in actions" :key="action.label" v-bind="action">
							{{ action.label }}
						</Button>
					</div>
				</slot>
			</div>
		</slot>
	</div>
</template>

<script setup lang="ts">
import { computed, reactive, type Component } from "vue"
import { type RouteLocation } from "vue-router"
import { Button, FeatherIcon } from "frappe-ui"
import LucideX from "~icons/lucide/x"

type Theme = "gray" | "blue" | "green" | "red"
type Size = "sm" | "md" | "lg" | "xl" | "2xl"
type Variant = "solid" | "subtle" | "outline" | "ghost"

interface ButtonProps {
	theme?: Theme
	size?: Size
	variant?: Variant
	label?: string
	icon?: string | Component
	iconLeft?: string | Component
	iconRight?: string | Component
	loading?: boolean
	loadingText?: string
	disabled?: boolean
	route?: RouteLocation
	link?: string
}

type DialogIcon = {
	name: string
	appearance?: "warning" | "info" | "danger" | "success"
}

type DialogOptions = {
	title?: string
	message?: string
	// default size = 'lg'
	size?: "xs" | "sm" | "md" | "lg" | "xl" | "2xl" | "3xl" | "4xl" | "5xl" | "6xl" | "7xl"
	icon?: DialogIcon | string
	actions?: Array<DialogAction>
	// default position = 'center'
	position?: "top" | "center"
}

type DialogActionContext = {
	close: () => void
}
type DialogAction = ButtonProps & {
	onClick?: (context: DialogActionContext) => void | Promise<void>
}

interface DialogProps {
	modelValue: boolean
	options?: DialogOptions
	disableOutsideClickToClose?: boolean
}

// Type for dialog action with reactive loading state
type ReactiveDialogAction = DialogAction & {
	loading: boolean
}

const props = withDefaults(defineProps<DialogProps>(), {
	options: () => ({}),
	disableOutsideClickToClose: false,
})

const emit = defineEmits<{
	(event: "update:modelValue", value: boolean): void
	(event: "close"): void
	(event: "after-leave"): void
}>()

const actions = computed((): ReactiveDialogAction[] => {
	let actions = props.options.actions
	if (!actions?.length) return []

	return actions.map((action) => {
		let _action = reactive({
			...action,
			loading: false,
			onClick: !action.onClick
				? close
				: async () => {
						_action.loading = true
						try {
							if (action.onClick) {
								// deprecated: uncomment this when we remove the backwards compatibility
								// let context: DialogActionContext = { close }
								type BackwardsCompatibleDialogActionContext = (() => void) & DialogActionContext

								let backwardsCompatibleContext = (() => {
									console.warn(
										"Value passed to onClick is a context object. Please use context.close() instead of context() to close the dialog.",
									)
									close()
								}) as BackwardsCompatibleDialogActionContext
								backwardsCompatibleContext.close = close
								await action.onClick(backwardsCompatibleContext)
							}
						} finally {
							_action.loading = false
						}
					},
		})
		return _action
	})
})

const isOpen = computed({
	get() {
		return props.modelValue
	},
	set(val: boolean) {
		emit("update:modelValue", val)
		if (!val) {
			emit("close")
		}
	},
})

function handleOpenChange(open: boolean) {
	isOpen.value = open
}

function close() {
	isOpen.value = false
}

const icon = computed(() => {
	if (!props.options?.icon) return null

	let icon = props.options.icon
	if (typeof icon === "string") {
		icon = { name: icon }
	}
	return icon as DialogIcon
})

const dialogPositionClasses = computed(() => {
	const position = props.options?.position || "center"
	const classMap: Record<string, string> = {
		center: "justify-center",
		top: "pt-[20vh]",
	}
	return classMap[position]
})

const dialogIconBgClasses = computed(() => {
	const appearance = icon.value?.appearance
	if (!appearance) return "bg-surface-gray-2"
	const classMap: Record<string, string> = {
		warning: "bg-surface-amber-2",
		info: "bg-surface-blue-2",
		danger: "bg-surface-red-2",
		success: "bg-surface-green-2",
	}
	return classMap[appearance]
})

const dialogIconClasses = computed(() => {
	const appearance = icon.value?.appearance
	if (!appearance) return "text-ink-gray-5"
	const classMap: Record<string, string> = {
		warning: "text-ink-amber-3",
		info: "text-ink-blue-3",
		danger: "text-ink-red-4",
		success: "text-ink-green-3",
	}
	return classMap[appearance]
})
</script>
