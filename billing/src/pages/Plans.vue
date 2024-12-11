<template>
	<header class="flex h-10.5 border-b items-center justify-between py-2 px-5 shrink-0">
		<Breadcrumbs :items="[{ label: 'Plans' }]" />
	</header>
	<div class="flex flex-col overflow-hidden px-60 pt-6">
		<ListView
			v-if="rows.length"
			:columns="columns"
			:rows="rows"
			row-key="name"
			:options="{
				selectable: false,
				showTooltip: false,
			}"
		>
			<ListHeader />
			<ListRows>
				<ListRow
					v-for="row in rows"
					:key="row.name"
					v-slot="{ column, item }"
					:row="row"
					:class="{ 'bg-gray-50 rounded': row.isCurrent }"
				>
					<ListRowItem :item="item" :align="column.align">
						<Badge
							v-if="column.key == 'upgrade' && row.isCurrent"
							class="shrink-0 bg-white"
							label="Current plan"
							variant="outline"
							size="lg"
						/>
						<Button
							v-else-if="column.key == 'upgrade' && !row.isCurrent"
							:label="row.downgrade ? 'Downgrade' : 'Upgrade'"
							@click="row.onClick"
							:disabled="!row.downgradable && row.downgrade"
						/>
						<div
							v-if="column.key == 'price'"
							class="text-base text-gray-900 font-semibold"
						>
							<span v-if="row.isTrial" class=""> Free trial </span>
							<span v-else>
								<span>{{ item.currency }} {{ item.label }}</span>
								<span class="text-gray-700 font-normal">/mo</span>
							</span>
						</div>
						<Tooltip v-if="column.key == 'info'">
							<template #body>
								<PlanDetails :plan="item" />
							</template>
							<FeatherIcon class="h-4 cursor-pointer" name="info" />
						</Tooltip>
					</ListRowItem>
				</ListRow>
			</ListRows>
		</ListView>
		<div v-else class="flex flex-1 items-center justify-center">
			<Spinner class="size-8" />
		</div>
		<UpgradePlanStepsModal
			v-if="showUpgradePlanStepsModal"
			v-model="showUpgradePlanStepsModal"
			:defaultStep="defaultStep"
			:plan="plan"
			@success="() => emit('success')"
		/>
	</div>
</template>
<script setup>
import PlanDetails from '@/components/PlanDetails.vue'
import UpgradePlanStepsModal from '@/components/UpgradePlanStepsModal.vue'
import {
	ListView,
	ListHeader,
	ListRows,
	ListRow,
	ListRowItem,
	Badge,
	Spinner,
	Button,
	FeatherIcon,
	Tooltip,
	createResource,
	Breadcrumbs,
} from 'frappe-ui'
import { createDialog } from '@/dialogs'
import { parseSize, ConfirmMessage } from '@/utils'
import { ref, computed, provide, inject, markRaw, h } from 'vue'

const emit = defineEmits(['success'])

const team = inject('team')
const currentSiteInfo = inject('currentSiteInfo')

const billingDetails = createResource({
	url: 'frappe.integrations.frappe_providers.frappecloud_billing.api',
	params: { method: 'billing.get_information' },
	cache: 'billingDetails',
	auto: true,
})

const plans = createResource({
	url: 'frappe.integrations.frappe_providers.frappecloud_billing.api',
	params: { method: 'site.get_plans' },
	cache: 'plans',
	auto: true,
})

const currentPlan = computed(() => {
	if (!currentSiteInfo.data) return null
	return currentSiteInfo.data.plan?.name || 'Trial'
})

const currency = computed(() => {
	if (!team.data) return 'INR'
	return team.data.currency || 'INR'
})

const columns = [
	{
		label: '',
		key: 'info',
		width: '8px',
	},
	{
		label: 'Cost',
		key: 'price',
		width: 0.8,
	},
	{
		label: 'CPU',
		key: 'cpu',
		width: 1.2,
	},
	{
		label: 'Memory',
		key: 'memory',
		width: 1.2,
	},
	{
		label: 'Disk',
		key: 'disk',
		width: 0.7,
	},
	{
		label: '',
		key: 'upgrade',
		width: 0.8,
		align: 'right',
	},
]

const rows = computed(() => {
	if (!currentPlan.value) return []
	if (!plans.data) return []
	let currentPlanIndex = plans.data.findIndex((plan) => plan.name === currentPlan.value)
	return plans.data
		.map((plan, i) => {
			let cpu = plan.cpu_time_per_day > 1 ? 'compute hrs/day' : 'compute hr/day'
			let price = currency.value === 'INR' ? plan.price_inr : plan.price_usd
			return {
				name: plan.name,
				price: {
					label: price.toString(),
					currency: currency.value === 'INR' ? '₹' : '$',
				},
				cpu: `${plan.cpu_time_per_day} ${cpu}`,
				memory: `${parseSize(plan.max_database_usage)} Database`,
				disk: `${parseSize(plan.max_storage_usage)} Disk`,
				info: plan,
				isCurrent: plan.name === currentPlan.value,
				isTrial: plan.is_trial_plan,
				downgradable: plan.allow_downgrading_from_other_plan,
				downgrade: currentPlanIndex > i,
				onClick: () => changePlan(plan, price.toString()),
			}
		})
		.filter((row) => !row.isTrial || (row.isTrial && row.name === currentPlan.value))
})

const defaultStep = ref(1)
const showUpgradePlanStepsModal = ref(false)
const plan = ref({
	name: '',
	price: '',
	currency: '',
})

function changePlan(_plan, price) {
	if (!billingDetails.data?.country || !team.data.payment_mode) {
		defaultStep.value = billingDetails.data.country ? 2 : 1
		showUpgradePlanStepsModal.value = true
		plan.value = {
			name: _plan.name,
			price,
			currency: currency.value === 'INR' ? '₹' : '$',
		}
		return
	}

	createDialog({
		title: 'Change plan',
		component: markRaw(
			h(ConfirmMessage, { price, currency: currency.value === 'INR' ? '₹' : '$' })
		),
		actions: [
			{
				label: 'Change plan',
				variant: 'solid',
				onClick: (close) => changePlanRequest(_plan.name, close),
			},
		],
	})
}

function changePlanRequest(planName, close) {
	createResource({
		url: 'frappe.integrations.frappe_providers.frappecloud_billing.api',
		params: { method: 'site.change_plan', data: { plan: planName } },
		auto: true,
		onSuccess: () => {
			currentSiteInfo.reload()
			plans.reload()
			close()
		},
	})
}

provide('plans', plans)
</script>
