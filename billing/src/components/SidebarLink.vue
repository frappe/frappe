<template>
	<button
		class="flex h-7 cursor-pointer items-center rounded text-gray-700 duration-300 ease-in-out focus:outline-none focus:transition-none focus-visible:rounded focus-visible:ring-2 focus-visible:ring-gray-400"
		:class="isActive ? 'bg-white shadow-sm' : 'hover:bg-gray-100'"
		@click="handleClick"
	>
		<div class="flex px-2 py-1 w-full items-center justify-between duration-300 ease-in-out">
			<div class="flex items-center truncate">
				<slot name="icon">
					<span class="grid flex-shrink-0 place-items-center">
						<FeatherIcon
							v-if="typeof icon == 'string'"
							:name="icon"
							class="size-4 text-gray-700"
						/>
						<component v-else :is="icon" class="size-4 text-gray-700" />
					</span>
				</slot>
				<span
					class="flex-1 ml-2 w-auto flex-shrink-0 truncate text-sm duration-300 ease-in-out"
				>
					{{ label }}
				</span>
			</div>
			<slot name="right">
				<FeatherIcon
					v-if="onClick && !noExternalLinkIcon"
					name="external-link"
					class="size-3 text-gray-500"
				/>
			</slot>
		</div>
	</button>
</template>

<script setup>
import { FeatherIcon } from 'frappe-ui'
import { computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'

const router = useRouter()
const route = useRoute()

const props = defineProps({
	icon: {
		type: [Object, String],
	},
	label: {
		type: String,
		default: '',
	},
	to: {
		type: [Object, String],
		default: '',
	},
	onClick: {
		type: Function,
		default: null,
	},
	noExternalLinkIcon: {
		type: Boolean,
		default: false,
	},
})

function handleClick() {
	if (!props.to && props.onClick) {
		props.onClick()
		return
	}
	if (typeof props.to === 'object') {
		router.push(props.to)
	} else {
		router.push({ name: props.to })
	}
}

let isActive = computed(() => {
	if (route.query.view) {
		return route.query.view == props.to?.query?.view
	}
	return route.name === props.to
})
</script>
