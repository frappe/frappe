<template>
	<div>
		<Button
			class="flex justify-between w-full rounded text-base"
			variant="ghost"
			:label="label"
			@click="onClick"
		>
			<template v-if="active" #suffix>
				<FeatherIcon class="size-4" name="check" />
			</template>
		</Button>
	</div>
</template>
<script setup>
import { Button, FeatherIcon } from 'frappe-ui'
const props = defineProps({
	label: String,
	active: Boolean,
	onClick: Array,
})
</script>
