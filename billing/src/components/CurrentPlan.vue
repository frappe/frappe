<template>
	<div class="flex flex-col gap-4">
		<div class="text-lg font-semibold text-gray-900">
			{{ 'Current plan' }}
		</div>
		<div
			v-if="currentPlan?.is_trial_plan"
			class="flex justify-between shadow rounded-lg py-3 px-4 text-base"
		>
			<div class="flex gap-3">
				<div class="flex flex-col gap-4 flex-1">
					<div class="flex flex-col gap-1.5">
						<div class="font-semibold text-gray-900 text-lg">
							{{ currentPlan.is_trial_plan ? 'Trial plan' : currentPlan.name }}
						</div>
						<div v-if="currentPlan.is_trial_plan" class="text-gray-700">
							{{ trialDescription }}
						</div>
					</div>
					<div
						v-if="currentPlan.is_trial_plan && currentPlan.support_included"
						class="text-gray-700 inline-flex items-center gap-1.5"
					>
						<FeatherIcon class="h-4" name="info" />
						<span> Support Included </span>
					</div>
					<div v-else class="text-gray-700">
						<span>{{ currency }}{{ price.value }}</span>
						<span class="font-normal">{{ ' / month · See plan details' }}</span>
					</div>
				</div>
			</div>
			<Button
				variant="solid"
				:label="currentPlan.is_trial_plan ? 'Upgrade now' : 'Change plan'"
				@click="emit('changePlan')"
			/>
		</div>
		<div
			v-else-if="currentPlan"
			class="flex flex-col shadow rounded-lg text-base text-gray-900"
		>
			<div class="flex flex-col gap-2.5 py-3 px-4">
				<div class="flex justify-between items-center">
					<div class="flex flex-col gap-1.5">
						<div class="font-semibold text-lg">Recurring Charges</div>
						<div class="text-gray-700">
							<span>Next charge date — </span>
							<span>{{ currentMonthEnd() }}</span>
							<span> · </span>
							<Tooltip>
								<template #body>
									<PlanDetails :plan="currentPlan" />
								</template>
								<span class="hover:underline cursor-pointer">
									See plan details
								</span>
							</Tooltip>
						</div>
					</div>
					<div class="flex flex-col gap-1.5 text-end">
						<div>
							<span class="font-semibold text-xl"> {{ currency }}{{ price }} </span>
							<span>/mo</span>
						</div>
						<div class="text-gray-600">
							<span>{{ currency }}{{ (price / 30).toFixed(2) }}</span>
							<span>/day</span>
						</div>
					</div>
				</div>
				<div class="flex justify-between items-center">
					<div class="text-gray-700 flex gap-2">
						<CardIcon class="h-4 w-4" />
						<div>
							<span>Current billing amount so far </span>
							<span class="text-gray-900 font-medium">
								{{ currency }} {{ currentBillingAmount?.toFixed(2) || '0.00' }}
							</span>
						</div>
					</div>
					<div>
						<Button variant="solid" label="Upgrade plan" @click="emit('changePlan')" />
					</div>
				</div>
			</div>
			<div
				v-if="unpaidAmount.data"
				class="flex justify-between items-center rounded-lg py-2 px-2.5 m-1.5 bg-gray-50"
			>
				<div class="text-gray-800 flex items-center gap-2 h-7">
					<UnPaidBillIcon class="h-4 w-4" />
					<div>
						<span>Unpaid amount is </span>
						<span>{{ currency }} {{ unpaidAmount.data?.toFixed(2) }}</span>
					</div>
				</div>
				<div>
					<Button variant="outline" label="Pay now" @click="payNow" />
				</div>
			</div>
		</div>
		<div v-else class="flex items-start justify-center">
			<Spinner class="h-4 w-4 text-gray-700" />
		</div>
		<AddPrepaidCreditsModal
			v-if="showAddPrepaidCreditsModal"
			v-model="showAddPrepaidCreditsModal"
			@success="upcomingInvoice.reload()"
		/>
	</div>
</template>
<script setup>
import CardIcon from '../icons/CardIcon.vue'
import UnPaidBillIcon from '../icons/UnPaidBillIcon.vue'
import PlanDetails from './PlanDetails.vue'
import AddPrepaidCreditsModal from './AddPrepaidCreditsModal.vue'
import { Button, Tooltip, Spinner, FeatherIcon, createResource } from 'frappe-ui'
import { calculateTrialEndDays } from '../utils.js'
import { ref, computed, inject } from 'vue'
import { useRouter } from 'vue-router'
import { createDialog } from '../dialogs.js'

const emit = defineEmits(['changePlan'])

const router = useRouter()

const team = inject('team')
const currentSiteInfo = inject('currentSiteInfo')
const { currentBillingAmount, upcomingInvoice } = inject('billing')

const showAddPrepaidCreditsModal = ref(false)

const trialEndDays = ref(0)
const trialDescription = computed(() => {
	return trialEndDays.value > 1
		? 'Your trial plan ends in ' + trialEndDays.value + ' days'
		: 'Your trial plan will end tomorrow'
})

const price = ref(null)
const currency = computed(() => (team.data.currency == 'INR' ? '₹' : '$'))

const currentPlan = computed(() => {
	if (!currentSiteInfo.data) return null
	trialEndDays.value = calculateTrialEndDays(currentSiteInfo.data.trial_end_date)
	let _currentPlan = currentSiteInfo.data.plan
	price.value = currency.value === '₹' ? _currentPlan.price_inr : _currentPlan.price_usd
	return _currentPlan
})

const unpaidAmount = createResource({
	url: 'frappe.integrations.frappe_providers.frappecloud_billing.api',
	params: { method: 'billing.total_unpaid_amount' },
	cache: 'unpaidAmount',
	auto: true,
})

const currentMonthEnd = () => {
	const date = new Date()
	const lastDay = new Date(date.getFullYear(), date.getMonth() + 1, 0)
	return lastDay.toLocaleDateString('en-US', {
		day: 'numeric',
		month: 'short',
		year: 'numeric',
	})
}

const unpaidInvoices = createResource({
	url: 'frappe.integrations.frappe_providers.frappecloud_billing.api',
	params: { method: 'billing.get_unpaid_invoices' },
})

function payNow() {
	team.data.payment_mode == 'Prepaid Credits'
		? (showAddPrepaidCreditsModal.value = true)
		: payUnpaidInvoices()
}

async function payUnpaidInvoices() {
	let _unpaidInvoices = await unpaidInvoices.reload()
	if (_unpaidInvoices.length > 1) {
		createDialog({
			title: 'Multiple unpaid invoices',
			message: 'You have multiple unpaid invoices. Please pay them from the invoices page',
			actions: [
				{
					label: 'Go to invoices',
					variant: 'solid',
					onClick: (close) => {
						router.push({ name: 'Invoices' })
						close()
					},
				},
			],
		})
	} else {
		let invoice = _unpaidInvoices
		if (invoice.stripe_invoice_url) {
			window.open(invoice.stripe_invoice_url, '_blank')
		} else {
			createResource({
				url: 'frappe.integrations.frappe_providers.frappecloud_billing.api',
				params: {
					method: 'billing.get_stripe_payment_url_for_invoice',
					data: { name: invoice.name },
				},
				auto: true,
				onSuccess: (url) => window.open(url, '_blank'),
			})
		}
	}
}
</script>
