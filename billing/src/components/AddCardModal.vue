<template>
	<Dialog v-model="show" :options="{ title: 'Add new card' }">
		<template #body-content>
			<div v-if="showMessage" class="inline-flex gap-1.5 text-base mb-5 text-gray-700">
				<FeatherIcon class="h-4" name="info" />
				<span> Add at least one card before changing the payment mode. </span>
			</div>
			<CardForm
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
import CardForm from './CardForm.vue'
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
