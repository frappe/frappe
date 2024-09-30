<template>
	<div class="min-h-screen w-full bg-black p-4">
		<h1 class="mb-4 text-2xl font-bold text-white">{{ title }}</h1>
		<div class="flex flex-col space-y-2">
			<AvatarCard
				v-for="card in cards"
				class="cursor-pointer"
				:key="card[rowKey]"
				:imageURL="card.imageURL"
				:title="card.title"
				:subtitle="card.subtitle"
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
