<template>
	<header class="flex h-10.5 border-b items-center justify-between py-2 px-5 shrink-0">
		<Breadcrumbs :items="[{ label: 'Cards' }]" />
	</header>
	<div class="flex flex-col overflow-hidden mx-60 mt-6">
		<div class="flex justify-end gap-2 mb-3">
			<Button :loading="cards.loading" @click="cards.reload()">
				<template #icon>
					<RefreshIcon class="h-4 w-4" />
				</template>
			</Button>
			<Button label="Add Card" variant="solid" @click="showAddCardModal = true">
				<template #prefix>
					<FeatherIcon name="plus" class="h-4 w-4" />
				</template>
			</Button>
		</div>
		<ListView
			:columns="columns"
			:rows="rows"
			row-key="id"
			:options="{
				selectable: false,
				showTooltip: false,
			}"
		>
			<ListHeader />
			<ListRows v-if="rows.length">
				<ListRow v-for="row in rows" :key="row.id" v-slot="{ column, item }" :row="row">
					<ListRowItem :item="item" :align="column.align">
						<div
							v-if="column.key == 'last_4'"
							class="flex items-center gap-2 text-base"
						>
							<component :is="cardBrandIcon(item.brand)" class="h-6 w-6" />
							<div>{{ item.last_4 }}</div>
							<Badge
								v-if="item.default"
								label="Default"
								variant="outline"
								theme="green"
							/>
						</div>
						<Dropdown
							v-else-if="column.key == 'actions' && !item.is_default"
							:options="item.options"
						>
							<button
								class="flex items-center rounded bg-gray-100 px-1 py-0.5 hover:bg-gray-200"
							>
								<FeatherIcon name="more-horizontal" class="h-4 w-4" />
							</button>
						</Dropdown>
					</ListRowItem>
				</ListRow>
			</ListRows>
			<div v-else class="h-60 border border-dashed rounded">
				<div class="flex flex-col gap-2 items-center justify-center h-full">
					<p class="text-lg text-gray-500">No card found</p>
					<Button label="Add Card" variant="outline" @click="showAddCardModal = true">
						<template #prefix>
							<FeatherIcon name="plus" class="h-4 w-4" />
						</template>
					</Button>
				</div>
			</div>
		</ListView>
	</div>
	<AddCardModal
		v-if="showAddCardModal"
		v-model="showAddCardModal"
		@success="
			() => {
				showAddCardModal = false
				cards.reload()
			}
		"
	/>
</template>
<script setup>
import AddCardModal from '@/components/AddCardModal.vue'
import RefreshIcon from '@/icons/RefreshIcon.vue'
import {
	ListView,
	ListHeader,
	ListRows,
	ListRow,
	ListRowItem,
	Dropdown,
	Button,
	Badge,
	Tooltip,
	FeatherIcon,
	createResource,
	Breadcrumbs,
} from 'frappe-ui'
import { useTimeAgo } from '@vueuse/core'
import { createDialog } from '@/dialogs.js'
import { cardBrandIcon } from '@/utils'
import { ref, computed } from 'vue'

const showAddCardModal = ref(false)

const cards = createResource({
	url: 'frappe.integrations.frappe_providers.frappecloud_billing.api',
	params: { method: 'billing.get_payment_methods' },
	cache: 'cards',
	auto: true,
})

const columns = [
	{
		label: 'Name on Card',
		key: 'name_on_card',
	},
	{
		label: 'Card',
		key: 'last_4',
		width: 1.3,
	},
	{
		label: 'Expiry',
		key: 'expiry_month',
		width: 0.7,
	},
	{
		label: 'Mandated',
		key: 'stripe_mandate_id',
		align: 'center',
		width: 0.5,
	},
	{
		label: '',
		key: 'alert',
		align: 'right',
		width: 0.3,
	},
	{
		label: '',
		key: 'creation',
		align: 'right',
		width: 0.7,
	},
	{
		label: '',
		key: 'actions',
		align: 'right',
		width: 0.3,
	},
]

const rows = computed(() => {
	if (!cards.data) return []
	return cards.data.map((card) => {
		return {
			id: card.name,
			name_on_card: card.name_on_card,
			last_4: {
				brand: card.brand,
				last_4: `•••• ${card.last_4}`,
				default: card.is_default,
			},
			expiry_month: `${
				card.expiry_month < 10 ? `0${card.expiry_month}` : card.expiry_month
			}/${card.expiry_year}`,
			stripe_mandate_id: card.stripe_mandate_id
				? h(FeatherIcon, {
						name: 'check-circle',
						class: 'h-4 w-4 text-green-600',
				  })
				: null,
			alert:
				card.is_default && card.stripe_payment_method
					? h(
							Tooltip,
							{
								text: 'The last payment failed on this card. Please use a different card.',
							},
							() =>
								h(FeatherIcon, {
									name: 'alert-circle',
									class: 'h-4 w-4 text-red-600',
								})
					  )
					: null,
			creation: useTimeAgo(card.creation).value,
			actions: {
				is_default: card.is_default,
				options: [
					{
						label: 'Set as default',
						onClick: () => setAsDefault(card.name),
						condition: () => !card.is_default,
					},
					{
						label: 'Remove',
						onClick: () => removeCard(card.name),
					},
				],
			},
		}
	})
})

const setAsDefault = (card) => {
	createResource({
		url: 'frappe.integrations.frappe_providers.frappecloud_billing.api',
		params: { method: 'billing.set_as_default', data: { name: card } },
		auto: true,
		onSuccess: () => {
			cards.reload()
		},
	})
}

const removeCard = (card) => {
	createDialog({
		title: 'Remove Card',
		message: 'Are you sure you want to remove this card?',
		actions: [
			{
				label: 'Remove',
				variant: 'solid',
				theme: 'red',
				onClick: (close) => {
					createResource({
						url: 'frappe.integrations.frappe_providers.frappecloud_billing.api',
						params: {
							method: 'billing.remove_payment_method',
							data: { name: card },
						},
						auto: true,
						onSuccess: () => {
							cards.reload()
							close()
						},
					})
				},
			},
		],
	})
}
</script>
