<template>
	<Dialog v-model="show" :options="{ title: 'Add Credit Balance' }">
		<template #body-content>
			<div v-if="showMessage" class="inline-flex gap-1.5 text-base mb-5 text-gray-700">
				<FeatherIcon class="h-4" name="info" />
				<span> Add credits to your account before changing the payment mode. </span>
			</div>
			<PrepaidCreditsForm
				@success="
					() => {
						show = false
						emit('success')
					}
				"
			/>
		</template>
	</Dialog>
</template>
<script setup>
import PrepaidCreditsForm from './PrepaidCreditsForm.vue'
import { Dialog, FeatherIcon } from 'frappe-ui'

const props = defineProps({
	showMessage: {
		type: Boolean,
		default: false,
	},
})

const emit = defineEmits(['success'])
const show = defineModel()
</script>
