<template>
	<Dialog v-model="show" :options="{ title: 'Billing Details' }">
		<template #body-content>
			<div v-if="showMessage" class="inline-flex gap-1.5 text-base mb-5 text-gray-700">
				<FeatherIcon class="h-4" name="info" />
				<span> Add billing details to your account before proceeding.</span>
			</div>
			<BillingDetails
				ref="billingRef"
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
import BillingDetails from './BillingDetails.vue'
import { FeatherIcon, Dialog } from 'frappe-ui'
import { ref } from 'vue'

const props = defineProps({
	showMessage: {
		type: Boolean,
		default: false,
	},
})
const emit = defineEmits(['success'])
const show = defineModel()
const billingRef = ref(null)
</script>
