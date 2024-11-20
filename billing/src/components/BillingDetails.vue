<template>
	<div class="flex flex-col gap-5">
		<FormControl
			v-model="billingInformation.billing_name"
			type="text"
			name="billing_name"
			label="Billing Name"
			:required="true"
		/>
		<AddressForm
			ref="addressFormRef"
			v-model="billingInformation"
			@success="() => emit('success')"
		/>
		<ErrorMessage class="mt-2" :message="errorMessage" />
	</div>
	<div v-if="addressFormRef" class="mt-6">
		<Button
			class="w-full"
			variant="solid"
			label="Update billing details"
			:loading="addressFormRef.updateBillingInformation.loading"
			@click="updateBillingInformation"
		/>
	</div>
</template>
<script setup>
import AddressForm from './AddressForm.vue'
import { FormControl, ErrorMessage, Button, createResource } from 'frappe-ui'
import { reactive, ref } from 'vue'

const emit = defineEmits(['success'])

const addressFormRef = ref(null)

const billingInformation = reactive({
	billing_name: '',
	address: '',
	city: '',
	state: '',
	postal_code: '',
	country: '',
	gstin: '',
})

createResource({
	url: 'frappe.integrations.frappe_providers.frappecloud_billing.api',
	params: { method: 'billing.get_information' },
	auto: true,
	onSuccess: (data) => {
		Object.assign(billingInformation, {
			address: data.address_line1,
			city: data.city,
			state: data.state,
			postal_code: data.pincode,
			country: data.country,
			gstin: data.gstin == 'Not Applicable' ? '' : data.gstin,
			billing_name: data.billing_name,
		})
	},
})

const errorMessage = ref('')

function updateBillingInformation() {
	if (!billingInformation.billing_name) {
		errorMessage.value = 'Billing Name is required'
		return
	}
	addressFormRef.value.updateBillingInformation.submit()
}
</script>
