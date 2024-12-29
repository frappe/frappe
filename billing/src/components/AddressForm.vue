<template>
	<div>
		<div class="flex flex-col gap-5">
			<div
				v-for="section in sections"
				:key="section.name"
				class="grid gap-4"
				:class="'grid-cols-' + section.columns"
			>
				<div v-for="field in section.fields" :key="field.name">
					<FormControl
						v-model="billingInformation[field.fieldname]"
						:label="field.label || field.fieldname"
						:type="getInputType(field)"
						:name="field.fieldname"
						:options="field.options"
						:required="field.required"
					/>
				</div>
			</div>
			<div v-show="billingInformation.country == 'India'">
				<FormControl label="I have GSTIN" type="checkbox" v-model="gstApplicable" />
				<FormControl
					v-if="gstApplicable"
					class="mt-5"
					label="GSTIN"
					type="text"
					v-model="billingInformation.gstin"
				/>
			</div>
		</div>
		<ErrorMessage class="mt-2" :message="updateBillingInformation.error" />
	</div>
</template>
<script setup>
import { FormControl, ErrorMessage, createResource, toast } from 'frappe-ui'
import { ref, computed, inject, watch } from 'vue'

const emit = defineEmits(['success'])
const team = inject('team')

const billingInformation = defineModel()

const updateBillingInformation = createResource({
	url: 'frappe.integrations.frappe_providers.frappecloud_billing.api',
	makeParams: () => {
		return {
			method: 'billing.update_information',
			data: { billing_details: billingInformation.value },
		}
	},
	validate: async () => {
		let error = await validate()
		if (error) return error
	},
	onSuccess: () => {
		toast({
			title: 'Billing Information Updated',
			icon: 'check',
			iconClasses: 'text-green-600',
			position: 'bottom-right',
		})
		emit('success')
	},
})

const gstApplicable = ref(false)

watch(
	() => billingInformation.value.gstin,
	(gstin) => {
		gstApplicable.value = gstin && gstin !== 'Not Applicable'
	}
)

async function validate() {
	// validate mandatory fields
	for (let field of sections.value.flatMap((s) => s.fields)) {
		if (field.required && !billingInformation.value[field.fieldname]) {
			return `${field.label} is required`
		}
	}

	if (!gstApplicable.value) {
		billingInformation.value.gstin = 'Not Applicable'
	}

	// validate gstin
	return await validateGST()
}

const _indianStates = [
	'Andaman and Nicobar Islands',
	'Andhra Pradesh',
	'Arunachal Pradesh',
	'Assam',
	'Bihar',
	'Chandigarh',
	'Chhattisgarh',
	'Dadra and Nagar Haveli and Daman and Diu',
	'Delhi',
	'Goa',
	'Gujarat',
	'Haryana',
	'Himachal Pradesh',
	'Jammu and Kashmir',
	'Jharkhand',
	'Karnataka',
	'Kerala',
	'Ladakh',
	'Lakshadweep Islands',
	'Madhya Pradesh',
	'Maharashtra',
	'Manipur',
	'Meghalaya',
	'Mizoram',
	'Nagaland',
	'Odisha',
	'Other Territory',
	'Puducherry',
	'Punjab',
	'Rajasthan',
	'Sikkim',
	'Tamil Nadu',
	'Telangana',
	'Tripura',
	'Uttar Pradesh',
	'Uttarakhand',
	'West Bengal',
]

const _countryList = createResource({
	url: 'frappe.integrations.frappe_providers.frappecloud_billing.api',
	params: { method: 'billing.country_list' },
	cache: 'countryList',
	auto: true,
	onSuccess: () => {
		let userCountry = team.data?.country
		if (userCountry) {
			let country = countryList.value?.find((d) => d.label === userCountry)
			if (country) {
				billingInformation.value.country = country.value
			}
		}
	},
})

const countryList = computed(() => {
	return (_countryList.data || []).map((d) => ({
		label: d.name,
		value: d.name,
	}))
})

const indianStates = computed(() => {
	return _indianStates.map((state) => ({
		label: state,
		value: state,
	}))
})

const sections = computed(() => {
	return [
		{
			name: 'Country and City',
			columns: 2,
			fields: [
				{
					fieldtype: 'Select',
					label: 'Country',
					fieldname: 'country',
					options: countryList.value,
					required: true,
				},
				{
					fieldtype: 'Data',
					label: 'City',
					fieldname: 'city',
					required: true,
				},
			],
		},
		{
			name: 'Address',
			columns: 1,
			fields: [
				{
					fieldtype: 'Data',
					label: 'Address',
					fieldname: 'address',
					required: true,
				},
			],
		},
		{
			name: 'State and Postal Code',
			columns: 2,
			fields: [
				{
					fieldtype: billingInformation.value.country === 'India' ? 'Select' : 'Data',
					label: 'State / Province / Region',
					fieldname: 'state',
					required: true,
					options:
						billingInformation.value.country === 'India' ? indianStates.value : null,
				},
				{
					fieldtype: 'Data',
					label: 'Postal Code',
					fieldname: 'postal_code',
					required: true,
				},
			],
		},
	]
})

function getInputType(field) {
	return {
		Data: 'text',
		Int: 'number',
		Select: 'select',
		Check: 'checkbox',
		Password: 'password',
		Text: 'textarea',
		Date: 'date',
	}[field.fieldtype || 'Data']
}

const _validateGST = createResource({
	url: 'frappe.integrations.frappe_providers.frappecloud_billing.api',
	makeParams() {
		return {
			method: 'billing.validate_gst',
			data: { address: billingInformation.value },
		}
	},
})

async function validateGST() {
	billingInformation.value.gstin = billingInformation.value.gstin || 'Not Applicable'
	await _validateGST.submit()
}

defineExpose({ updateBillingInformation, validate })
</script>
