<template>
	<div
		class="dialog-content my-8 inline-block w-full transform overflow-hidden rounded-xl bg-surface-elevation-1 text-start align-middle shadow-xl focus-visible:outline-none"
		:class="sizeClass"
	>
		<!-- bare: no chrome, render default slot directly -->
		<slot v-if="resolved.bare" :close="close" />

		<!-- legacy `#body` slot: full layout override (deprecated) -->
		<slot v-else-if="$slots.body" name="body" />

		<template v-else>
			<!-- legacy `#body-main`: full middle override (deprecated) -->
			<slot v-if="$slots['body-main']" name="body-main" />
			<div v-else class="bg-surface-elevation-1 px-4 pb-6 pt-5 sm:px-6">
				<div class="flex">
					<div class="w-full flex-1">
						<!-- legacy `#body-header` -->
						<slot v-if="$slots['body-header']" name="body-header" />
						<div v-else-if="showHeader" class="mb-6 flex items-center justify-between">
							<div class="flex flex-1 items-center space-x-2">
								<div
									v-if="resolvedIcon"
									class="flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-full"
									:class="dialogIconBgClasses"
								>
									<span
										v-if="isLucide(resolvedIcon.name)"
										:class="[resolvedIcon.name, 'size-4', dialogIconClasses]"
										aria-hidden="true"
									/>
									<FeatherIcon
										v-else
										:name="resolvedIcon.name"
										class="h-4 w-4"
										:class="dialogIconClasses"
										aria-hidden="true"
									/>
								</div>
								<header class="flex-1">
									<slot name="title" :close="close">
										<slot name="body-title">
											<h3 v-if="resolved.title" class="text-2xl-semibold leading-6 text-ink-gray-8">
												{{ resolved.title }}
											</h3>
										</slot>
									</slot>
								</header>
							</div>
							<div v-if="resolved.showCloseButton">
								<Button variant="ghost" label="Close" @click="close">
									<template #icon>
										<span class="lucide-x size-4 text-ink-gray-9" />
									</template>
								</Button>
							</div>
						</div>

						<slot name="body-content">
							<slot :close="close">
								<div v-if="resolved.message">
									<p class="text-p-base text-ink-gray-7">
										{{ resolved.message }}
									</p>
								</div>
							</slot>
						</slot>
					</div>
				</div>
			</div>

			<div v-if="reactiveActions.length || $slots.actions" class="px-4 pb-7 pt-4 sm:px-6">
				<slot name="actions" v-bind="{ close, actions: reactiveActions }">
					<div :class="isSingleActionFullWidth ? '' : 'flex justify-end gap-2'">
						<Button
							v-for="action in reactiveActions"
							:key="action.label"
							:class="isSingleActionFullWidth ? 'w-full' : ''"
							:disabled="action.disabled"
							v-bind="action"
						>
							{{ action.label }}
						</Button>
					</div>
				</slot>
			</div>
		</template>

		<!-- close button when auto-header is suppressed -->
		<div
			v-if="
				resolved.showCloseButton && !showHeader && !resolved.bare && !$slots['body'] && !$slots['body-header']
			"
		>
			<Button class="absolute right-4 top-4 z-10" variant="ghost" label="Close" @click="close">
				<template #icon>
					<span class="lucide-x size-4 text-ink-gray-9" />
				</template>
			</Button>
		</div>
	</div>
</template>
<script setup lang="ts">
import { computed, reactive, ref, useSlots, watchEffect } from "vue"
import { Button, FeatherIcon } from "frappe-ui"

type Theme = "gray" | "blue" | "green" | "red"
type Size = "sm" | "md" | "lg" | "xl" | "2xl"
type Variant = "solid" | "subtle" | "outline" | "ghost"

interface ButtonProps {
	theme?: Theme
	size?: Size
	variant?: Variant
	label?: string
	icon?: any
	iconLeft?: any
	iconRight?: any
	loading?: boolean
	loadingText?: string
	disabled?: boolean
	route?: any
	link?: string
}

type DialogIconAppearance = "warning" | "info" | "danger" | "success"
type DialogTheme = "blue" | "green" | "red" | "yellow"

type DialogIcon = {
	name: string
	appearance?: DialogIconAppearance
	theme?: DialogTheme
}

type DialogActionContext = {
	close: () => void
}
type DialogAction = ButtonProps & {
	onClick?: (context: DialogActionContext) => void | Promise<void>
}

type DialogOptions = {
	title?: string
	message?: string
	size?: "xs" | "sm" | "md" | "lg" | "xl" | "2xl" | "3xl" | "4xl" | "5xl" | "6xl" | "7xl"
	icon?: DialogIcon | string
	actions?: Array<DialogAction>
	position?: "top" | "center"
	paddingTop?: string
}

type DialogReactiveAction = DialogAction & {
	loading: boolean
}

interface DialogProps {
	open?: boolean
	modelValue?: boolean
	options?: DialogOptions
	title?: string
	message?: string
	icon?: DialogIcon | string
	size?: string
	position?: string
	paddingTop?: string
	actions?: Array<DialogAction>
	disableOutsideClickToClose?: boolean
	dismissible?: boolean
	showCloseButton?: boolean
	bare?: boolean
}

const props = withDefaults(defineProps<DialogProps>(), {
	open: undefined,
	modelValue: undefined,
	disableOutsideClickToClose: undefined,
	size: undefined,
	position: undefined,
	dismissible: true,
	showCloseButton: true,
	bare: false,
})

const emit = defineEmits<{
	(event: "update:open", value: boolean): void
	(event: "update:modelValue", value: boolean): void
	(event: "close"): void
	(event: "after-leave"): void
}>()

const allSlots = useSlots()

const resolved = computed(() => {
	const o = props.options || ({} as DialogOptions)
	return {
		title: props.title ?? o.title,
		message: props.message ?? o.message,
		icon: props.icon ?? o.icon,
		size: props.size ?? o.size ?? "lg",
		position: props.position ?? o.position ?? "center",
		paddingTop: props.paddingTop ?? o.paddingTop,
		actions: props.actions ?? o.actions ?? [],
		showCloseButton: props.showCloseButton,
		bare: props.bare,
	}
})

const isDismissible = computed(() => {
	if (props.disableOutsideClickToClose) return false
	return props.dismissible !== false
})

const sizeClass = computed(() => {
	const size = resolved.value.size
	const map: Record<string, string> = {
		xs: "max-w-xs",
		sm: "max-w-sm",
		md: "max-w-md",
		lg: "max-w-lg",
		xl: "max-w-xl",
		"2xl": "max-w-2xl",
		"3xl": "max-w-3xl",
		"4xl": "max-w-4xl",
		"5xl": "max-w-5xl",
		"6xl": "max-w-6xl",
		"7xl": "max-w-7xl",
	}
	return map[size] || "max-w-lg"
})

const isOpen = computed({
	get() {
		if (props.open !== undefined) return !!props.open
		return !!props.modelValue
	},
	set(val: boolean) {
		emit("update:open", val)
		emit("update:modelValue", val)
		if (!val) emit("close")
	},
})

function close() {
	isOpen.value = false
}

const resolvedIcon = computed<DialogIcon | null>(() => {
	const raw = resolved.value.icon
	if (!raw) return null
	if (typeof raw === "string") return { name: raw }
	return raw
})

const iconTheme = computed<DialogTheme | null>(() => {
	const icon = resolvedIcon.value
	if (!icon) return null
	if (icon.theme) return icon.theme
	const map: Record<DialogIconAppearance, DialogTheme> = {
		warning: "yellow",
		info: "blue",
		danger: "red",
		success: "green",
	}
	return icon.appearance ? map[icon.appearance] : null
})

const dialogIconBgClasses = computed(() => {
	const theme = iconTheme.value
	if (!theme) return "bg-surface-gray-2"
	const map: Record<DialogTheme, string> = {
		yellow: "bg-surface-amber-2",
		blue: "bg-surface-blue-2",
		red: "bg-surface-red-2",
		green: "bg-surface-green-2",
	}
	return map[theme]
})

const dialogIconClasses = computed(() => {
	const theme = iconTheme.value
	if (!theme) return "text-ink-gray-5"
	const map: Record<DialogTheme, string> = {
		yellow: "text-ink-amber-6",
		blue: "text-ink-blue-6",
		red: "text-ink-red-8",
		green: "text-ink-green-6",
	}
	return map[theme]
})

const dialogPositionClasses = computed(() => {
	if (resolved.value.paddingTop) return ""
	const position = resolved.value.position
	const map: Record<string, string> = {
		center: "justify-center",
		top: "pt-[20vh]",
	}
	return map[position] || "justify-center"
})

const dialogPositionStyles = computed(() => {
	if (resolved.value.paddingTop) {
		return { paddingTop: resolved.value.paddingTop }
	}
	return {}
})

const reactiveActions = computed((): DialogReactiveAction[] => {
	if (resolved.value.bare) return []
	const list = resolved.value.actions
	if (!list?.length) return []
	return list.map((action) => {
		const _action = reactive({
			...action,
			loading: false,
			onClick: !action.onClick
				? close
				: async () => {
						_action.loading = true
						try {
							type LegacyContext = (() => void) & DialogActionContext
							const ctx = (() => {
								close()
							}) as LegacyContext
							ctx.close = close
							await action.onClick!(ctx)
						} finally {
							_action.loading = false
						}
					},
		})
		return _action
	})
})

const isSingleActionFullWidth = computed(() => {
	const smallSizes = ["xs", "sm", "md"]
	return reactiveActions.value.length === 1 && smallSizes.includes(resolved.value.size as string)
})

const showHeader = computed(() => {
	if (resolved.value.bare) return false
	if (allSlots.title || allSlots["body-title"]) return true
	if (resolved.value.title) return true
	return false
})

function isLucide(name: string | undefined) {
	return name && name.startsWith("lucide-")
}

defineExpose({ close })
</script>
