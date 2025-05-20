<template>
	<div
		class="inline-block w-full transform overflow-hidden rounded-xl bg-surface-modal text-left align-middle shadow-xl transition-all"
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
											<svg
												width="16"
												height="16"
												viewBox="0 0 16 16"
												fill="none"
												xmlns="http://www.w3.org/2000/svg"
												class="text-ink-gray-9"
											>
												<path
													fill-rule="evenodd"
													clip-rule="evenodd"
													d="M12.8567 3.85355C13.052 3.65829 13.052 3.34171 12.8567 3.14645C12.6615 2.95118 12.3449 2.95118 12.1496 3.14645L8.00201 7.29405L3.85441 3.14645C3.65914 2.95118 3.34256 2.95118 3.1473 3.14645C2.95204 3.34171 2.95204 3.65829 3.1473 3.85355L7.29491 8.00116L3.14645 12.1496C2.95118 12.3449 2.95118 12.6615 3.14645 12.8567C3.34171 13.052 3.65829 13.052 3.85355 12.8567L8.00201 8.70827L12.1505 12.8567C12.3457 13.052 12.6623 13.052 12.8576 12.8567C13.0528 12.6615 13.0528 12.3449 12.8576 12.1496L8.70912 8.00116L12.8567 3.85355Z"
													fill="currentColor"
												/>
											</svg>
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
import { Button } from "frappe-ui"

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

const props = withDefaults(defineProps<DialogProps>(), {
	options: () => ({}),
	disableOutsideClickToClose: false,
})

const emit = defineEmits<{
	(event: "update:modelValue", value: boolean): void
	(event: "close"): void
	(event: "after-leave"): void
}>()

const actions = computed(() => {
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
								let backwardsCompatibleContext = function () {
									console.warn(
										"Value passed to onClick is a context object. Please use context.close() instead of context() to close the dialog.",
									)
									close()
								}
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
	set(val) {
		emit("update:modelValue", val)
		if (!val) {
			emit("close")
		}
	},
})

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
	return {
		center: "justify-center",
		top: "pt-[20vh]",
	}[position]
})

const dialogIconBgClasses = computed(() => {
	const appearance = icon.value?.appearance
	if (!appearance) return "bg-surface-gray-2"
	return {
		warning: "bg-surface-amber-2",
		info: "bg-surface-blue-2",
		danger: "bg-surface-red-2",
		success: "bg-surface-green-2",
	}[appearance]
})

const dialogIconClasses = computed(() => {
	const appearance = icon.value?.appearance
	if (!appearance) return "text-ink-gray-5"
	return {
		warning: "text-ink-amber-3",
		info: "text-ink-blue-3",
		danger: "text-ink-red-4",
		success: "text-ink-green-3",
	}[appearance]
})
</script>
