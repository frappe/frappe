<template>
	<div
		data-slot="content"
		class="dialog-content my-8 inline-block w-full transform overflow-hidden rounded-7 bg-surface-elevation-1 text-start align-middle shadow-xl focus-visible:outline-none"
		:class="sizeClass"
		:style="outOfFlowStyles"
		:data-position="position"
	>
		<slot v-if="bare" :close="close" />

		<template v-else>
			<div class="bg-surface-elevation-1 px-4 pb-6 pt-5 sm:px-6">
				<div class="flex">
					<div class="w-full flex-1">
						<div v-if="showHeader" class="mb-6 flex items-center justify-between">
							<div class="flex flex-1 items-center space-x-2">
								<div
									v-if="lucideIcon || componentIcon"
									data-slot="icon"
									class="flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-full"
									:class="iconBgClass"
								>
									<span v-if="lucideIcon" :class="[lucideIcon, 'size-4', iconClass]" aria-hidden="true" />
									<component
										:is="componentIcon"
										v-else
										class="size-4"
										:class="iconClass"
										aria-hidden="true"
									/>
								</div>
								<header class="flex-1">
									<slot name="title" :close="close">
										<h3 v-if="title" class="text-2xl-semibold leading-6 text-ink-gray-8">
											{{ title }}
										</h3>
									</slot>
								</header>
							</div>
							<Button v-if="showCloseButton" variant="ghost" label="Close" @click="close">
								<template #icon>
									<span class="lucide-x size-4 text-ink-gray-9" />
								</template>
							</Button>
						</div>

						<slot :close="close">
							<p v-if="message" class="text-p-base text-ink-gray-7">
								{{ message }}
							</p>
						</slot>
					</div>
				</div>
			</div>

			<div v-if="reactiveActions.length || $slots.actions" data-slot="actions" class="px-4 pb-7 pt-4 sm:px-6">
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

		<Button
			v-if="showCloseButton && !showHeader && !bare"
			class="absolute right-4 top-4 z-10"
			variant="ghost"
			label="Close"
			@click="close"
		>
			<template #icon>
				<span class="lucide-x size-4 text-ink-gray-9" />
			</template>
		</Button>
	</div>
</template>
<script setup lang="ts">
import { computed, reactive, useSlots } from "vue"
import { Button } from "frappe-ui"
import type { DialogProps, DialogReactiveAction, DialogTheme } from "frappe-ui"

const props = withDefaults(defineProps<DialogProps>(), {
	open: undefined,
	modelValue: undefined,
	size: "lg",
	position: "center",
	dismissible: true,
	showCloseButton: true,
	bare: false,
})

const emit = defineEmits<{
	"update:open": [value: boolean]
	"update:modelValue": [value: boolean]
	close: []
}>()

const slots = useSlots()

const sizeClass = computed(() => {
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
	return map[props.size] || "max-w-lg"
})

// Mimics the portal's viewport placement against the canvas instead
const outOfFlowStyles = computed(() => {
	const paddingTop = typeof props.paddingTop === "number" ? `${props.paddingTop}px` : props.paddingTop
	const top = paddingTop || props.position === "top"
	return {
		position: "absolute",
		left: "1.5rem",
		right: "1.5rem",
		top: top ? paddingTop || "20%" : "50%",
		width: "auto",
		margin: "0 auto",
		transform: top ? "none" : "translateY(-50%)",
	} as const
})

function close() {
	emit("update:open", false)
	emit("update:modelValue", false)
	emit("close")
}

const lucideIcon = computed(() =>
	typeof props.icon === "string" && props.icon.startsWith("lucide-") ? props.icon : null,
)
const componentIcon = computed(() => (props.icon && typeof props.icon !== "string" ? props.icon : null))

const iconBgClass = computed(() => {
	const map: Record<DialogTheme, string> = {
		amber: "bg-surface-amber-2",
		blue: "bg-surface-blue-2",
		red: "bg-surface-red-2",
		green: "bg-surface-green-2",
	}
	return props.theme ? map[props.theme] : "bg-surface-gray-2"
})

const iconClass = computed(() => {
	const map: Record<DialogTheme, string> = {
		amber: "text-ink-amber-5",
		blue: "text-ink-blue-5",
		red: "text-ink-red-7",
		green: "text-ink-green-5",
	}
	return props.theme ? map[props.theme] : "text-ink-gray-5"
})

const reactiveActions = computed((): DialogReactiveAction[] => {
	if (props.bare || !props.actions?.length) return []
	return props.actions.map((action) => {
		const _action = reactive({
			...action,
			loading: false,
			onClick: !action.onClick
				? close
				: async () => {
						_action.loading = true
						try {
							await action.onClick!({ close })
						} finally {
							_action.loading = false
						}
					},
		})
		return _action
	})
})

const isSingleActionFullWidth = computed(
	() => reactiveActions.value.length === 1 && ["xs", "sm", "md"].includes(props.size),
)

const showHeader = computed(() => !props.bare && Boolean(slots.title || props.title))
</script>
