<template>
	<div class="min-h-screen w-full bg-white p-4">
		<div class="mb-5 text-2xl font-bold text-gray-800">{{ title }}</div>
		<div class="flex flex-col space-y-2">
			<AvatarCard
				v-for="card in cards"
				class="cursor-pointer"
				:key="card[rowKey]"
				:imageURL="card.imageURL"
				:title="card.title"
				:subtitle="card.subtitle"
				:route="card.route"
				@click="
					() => {
						selectedCard = card
						$emit('onRowClick', card)
					}
				"
			/>
		</div>
	</div>
</template>

<script setup lang="ts">
import { ref } from "vue"
import type { PropType } from "vue"
import AvatarCard from "@/components/AppLayout/AvatarCard.vue"
import { AvatarCard as IAvatarCard } from "@/types/studioComponents"

const emit = defineEmits<{
	onRowClick: [card: IAvatarCard]
}>()

const props = defineProps({
	title: {
		type: String,
	},
	cards: {
		type: Array as PropType<IAvatarCard[]>,
		required: true,
	},
	rowKey: {
		type: String,
		default: "name",
	},
})

const selectedCard = ref<IAvatarCard | null>(null)
defineExpose({
	selectedCard,
})
</script>
