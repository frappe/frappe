<template>
	<Dialog v-model="show">
		<template #body-main>
			<div class="bg-white px-4 pb-6 pt-5 sm:px-6">
				<div class="flex items-center justify-between">
					<div class="flex flex-col w-full">
						<div class="flex justify-between items-center">
							<div class="inline-flex items-center gap-1.5 text-base text-gray-800">
								<div
									v-if="step > 1"
									class="-ml-0.5 cursor-pointer"
									@click="step = step - 1"
								>
									<FeatherIcon class="h-4.5" name="chevron-left" />
								</div>
								<span>Step {{ step }}/2</span>
							</div>
							<Button variant="ghost" @click="show = false">
								<template #icon>
									<FeatherIcon name="x" class="h-4 w-4" />
								</template>
							</Button>
						</div>
						<h3 class="text-2xl font-semibold leading-6 text-gray-900">
							{{ title || 'Untitled' }}
						</h3>
						<div
							class="my-5 h-px w-full"
							:class="[
								step === 1
									? 'bg-[linear-gradient(to_right,black_0%,black_50%,#ededed_50%,#ededed_100%)]'
									: 'bg-[linear-gradient(to_right,#ededed_0%,#ededed_50%,black_50%,black_100%)]',
							]"
						/>
					</div>
				</div>
				<div v-show="step === 1">
					<BillingDetails ref="billingRef" @success="() => (step = step + 1)" />
				</div>
				<div v-show="step === 2">
					<div class="text-sm text-gray-800 mb-7.5">
						<div class="mb-1.5">Payment mode</div>
						<TabButtons v-model="activeTab" :buttons="paymentModes" />
						<div class="flex gap-1.5 mt-2">
							<FeatherIcon class="h-4" name="info" />
							{{ paymentModes.find((m) => m.value == activeTab).description }}
						</div>
					</div>
					<CardForm v-show="activeTab == 'Card'" @success="updateMode" />
					<PrepaidCreditsForm
						v-show="activeTab == 'Prepaid Credits'"
						@success="updateMode"
					/>
				</div>
			</div>
		</template>
	</Dialog>
</template>
<script setup>
import BillingDetails from '@/components/BillingDetails.vue'
import CardForm from '@/components/CardForm.vue'
import PrepaidCreditsForm from '@/components/PrepaidCreditsForm.vue'
import { createDialog } from '@/dialogs'
import { ConfirmMessage } from '@/utils'
import { Dialog, Button, FeatherIcon, TabButtons, createResource } from 'frappe-ui'
import { ref, computed, inject, markRaw, h } from 'vue'

const props = defineProps({
	defaultStep: {
		type: Number,
		default: 1,
	},
	plan: {
		type: Object,
		required: true,
	},
})

const emit = defineEmits(['success'])

const currentSiteInfo = inject('currentSiteInfo')
const plans = inject('plans')

const show = defineModel()
const step = ref(props.defaultStep)
const title = computed(() => (step.value === 1 ? 'Billing Details' : 'Payment mode'))

const billingRef = ref(null)
const activeTab = ref('Card')

const paymentModes = [
	{
		label: 'Card',
		value: 'Card',
		description: 'Your card will be charged for monthly subscription',
	},
	{
		label: 'Prepaid credits',
		value: 'Prepaid Credits',
		description: 'You will be charged from your credit balance for monthly subscription',
	},
]

function updateMode() {
	show.value = false
	createResource({
		url: 'frappe.integrations.frappe_providers.frappecloud_billing.api',
		params: {
			method: 'billing.change_payment_mode',
			data: { mode: activeTab.value },
		},
		auto: true,
		onSuccess: () => upgradePlan(),
	})
}

function upgradePlan() {
	createDialog({
		title: 'Change plan',
		component: markRaw(
			h(ConfirmMessage, { price: props.plan.price, currency: props.plan.currency })
		),
		actions: [
			{
				label: 'Change plan',
				variant: 'solid',
				onClick: (close) => changePlanRequest(close),
			},
		],
	})
}

function changePlanRequest(close) {
	createResource({
		url: 'frappe.integrations.frappe_providers.frappecloud_billing.api',
		params: { method: 'site.change_plan', data: { plan: props.plan.name } },
		auto: true,
		onSuccess: () => {
			currentSiteInfo.reload()
			plans.reload()
			close()
			emit('success')
		},
	})
}
</script>
