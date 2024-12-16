<template>
	<div class="flex flex-col gap-4">
		<div class="text-lg font-semibold text-gray-900">
			{{ 'Payment details' }}
		</div>
		<div class="flex flex-col">
			<div
				v-if="team.data.payment_mode == 'Card'"
				class="flex justify-between items-center text-base text-gray-900"
			>
				<div class="flex flex-col gap-1.5">
					<div class="font-medium">{{ 'Active card' }}</div>
					<div class="overflow-hidden text-gray-700 text-ellipsis">
						<div
							v-if="team.data.payment_method"
							class="inline-flex items-center gap-2"
						>
							<component :is="cardBrandIcon(team.data.payment_method.brand)" />
							<div class="text-gray-700">
								<span>{{ team.data.payment_method.name_on_card }}</span>
								<span> &middot; Card ending in •••• </span>
								<span>{{ team.data.payment_method.last_4 }}</span>
							</div>
						</div>
						<span v-else class="text-gray-700">No card added</span>
					</div>
				</div>
				<div class="shrink-0">
					<Button
						:label="team.data.payment_method ? 'Change card' : 'Add card'"
						@click="changeMethod"
					>
						<template v-if="!team.data.payment_method" #prefix>
							<FeatherIcon class="h-4" name="plus" />
						</template>
					</Button>
				</div>
			</div>
			<div v-if="team.data.payment_mode == 'Card'" class="bg-gray-100 h-px my-3" />
			<div class="flex justify-between items-center text-base text-gray-900">
				<div class="flex flex-col gap-1.5">
					<div class="font-medium">{{ 'Mode of payment' }}</div>
					<div
						v-if="team.data.payment_mode"
						class="inline-flex items-center gap-2 text-gray-700"
					>
						<FeatherIcon class="h-4" name="info" />
						{{ paymentMode.description }}
					</div>
					<span v-else class="text-gray-700">Not set</span>
				</div>
				<div class="shrink-0">
					<Dropdown :options="paymentModeOptions">
						<template #default="{ open }">
							<Button
								:label="team.data.payment_mode ? paymentMode.label : 'Set mode'"
							>
								<template #suffix>
									<FeatherIcon
										:name="open ? 'chevron-up' : 'chevron-down'"
										class="h-4"
									/>
								</template>
							</Button>
						</template>
					</Dropdown>
				</div>
			</div>
			<div class="bg-gray-100 h-px my-3" />
			<div class="flex justify-between items-center text-base text-gray-900">
				<div class="flex flex-col gap-1.5">
					<div class="font-medium">{{ 'Credit balance' }}</div>
					<div class="text-gray-700">
						{{ availableCredits || currency + ' 0.00' }}
					</div>
				</div>
				<div class="shrink-0">
					<Button
						:label="'Add credit'"
						@click="
							() => {
								showMessage = false
								if (!billingDetailsSummary) {
									showMessage = true
									showBillingDetailsDialog = true
									return
								}
								showAddPrepaidCreditsModal = true
							}
						"
					>
						<template #prefix>
							<FeatherIcon class="h-4" name="plus" />
						</template>
					</Button>
				</div>
			</div>
			<div class="bg-gray-100 h-px my-3" />
			<div class="flex justify-between items-center text-base text-gray-900">
				<div class="flex flex-col gap-1.5">
					<div class="font-medium">{{ 'Billing address' }}</div>
					<div v-if="billingDetailsSummary" class="text-gray-700 leading-5">
						{{ billingDetailsSummary }}
					</div>
					<div v-else class="text-gray-700">No address</div>
				</div>
				<div class="shrink-0">
					<Button
						:label="billingDetailsSummary ? 'Edit information' : 'Add billing address'"
						@click="
							() => {
								showMessage = false
								showBillingDetailsDialog = true
							}
						"
					>
						<template v-if="!billingDetailsSummary" #prefix>
							<FeatherIcon class="h-4" name="plus" />
						</template>
					</Button>
				</div>
			</div>
		</div>
	</div>
	<BillingDetailsModal
		v-if="showBillingDetailsDialog"
		v-model="showBillingDetailsDialog"
		:showMessage="showMessage"
		@success="billingDetails.reload()"
	/>
	<AddPrepaidCreditsModal
		v-if="showAddPrepaidCreditsModal"
		v-model="showAddPrepaidCreditsModal"
		:showMessage="showMessage"
		@success="upcomingInvoice.reload()"
	/>
	<AddCardModal
		v-if="showAddCardModal"
		v-model="showAddCardModal"
		:showMessage="showMessage"
		@success="
			() => {
				showMessage = false
				showAddCardModal = false
				team.reload()
			}
		"
	/>
	<ChangeCardModal
		v-if="showChangeCardModal"
		v-model="showChangeCardModal"
		@addCard="
			() => {
				showChangeCardModal = false
				showAddCardModal = true
			}
		"
		@success="() => team.reload()"
	/>
</template>
<script setup>
import DropdownItem from './DropdownItem.vue'
import BillingDetailsModal from './BillingDetailsModal.vue'
import AddPrepaidCreditsModal from './AddPrepaidCreditsModal.vue'
import AddCardModal from './AddCardModal.vue'
import ChangeCardModal from './ChangeCardModal.vue'
import { Dropdown, Button, FeatherIcon, createResource } from 'frappe-ui'
import { cardBrandIcon } from '../utils.js'
import { computed, ref, inject, h } from 'vue'

const team = inject('team')
const { availableCredits, upcomingInvoice } = inject('billing')

const showBillingDetailsDialog = ref(false)
const showAddPrepaidCreditsModal = ref(false)
const showAddCardModal = ref(false)
const showChangeCardModal = ref(false)

const currency = computed(() => (team.data.currency == 'INR' ? '₹' : '$'))

const billingDetails = createResource({
	url: 'frappe.integrations.frappe_providers.frappecloud_billing.api',
	params: { method: 'billing.get_information' },
	cache: 'billingDetails',
	auto: true,
})

const billingDetailsSummary = computed(() => {
	let _billingDetails = billingDetails.data
	if (!_billingDetails) return ''

	const { billing_name, address_line1, city, state, country, pincode, gstin } =
		_billingDetails || {}
	return [billing_name, address_line1, city, state, country, pincode, gstin]
		.filter(Boolean)
		.join(', ')
})

const paymentModeOptions = [
	{
		label: 'Card',
		value: 'Card',
		description: 'Your card will be charged for monthly subscription',
		component: () =>
			h(DropdownItem, {
				label: 'Card',
				active: team.data.payment_mode === 'Card',
				onClick: () => updatePaymentMode('Card'),
			}),
	},
	{
		label: 'Prepaid credits',
		value: 'Prepaid Credits',
		description: 'You will be charged from your credit balance for monthly subscription',
		component: () =>
			h(DropdownItem, {
				label: 'Prepaid credits',
				active: team.data.payment_mode === 'Prepaid Credits',
				onClick: () => updatePaymentMode('Prepaid Credits'),
			}),
	},
]

const paymentMode = computed(() => {
	return paymentModeOptions.find((o) => o.value === team.data.payment_mode)
})

const showMessage = ref(false)
function updatePaymentMode(mode) {
	showMessage.value = false
	if (!billingDetailsSummary.value) {
		showMessage.value = true
		showBillingDetailsDialog.value = true
		return
	}
	if (mode === 'Prepaid Credits' && team.data.balance === 0) {
		showMessage.value = true
		showAddPrepaidCreditsModal.value = true
		return
	} else if (mode === 'Card' && !team.data.payment_method) {
		showMessage.value = true
		showAddCardModal.value = true
	}
	createResource({
		url: 'frappe.integrations.frappe_providers.frappecloud_billing.api',
		params: {
			method: 'billing.change_payment_mode',
			data: { mode },
		},
		auto: true,
		onSuccess: () => team.reload(),
	})
}

function changeMethod() {
	if (team.data.payment_method) {
		showChangeCardModal.value = true
	} else {
		showMessage.value = false
		showAddCardModal.value = true
	}
}
</script>
