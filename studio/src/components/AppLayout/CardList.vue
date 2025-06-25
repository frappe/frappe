<template>
	<div class="h-screen min-h-screen w-full flex-1 overflow-auto bg-white p-4">
		<div class="mb-5 text-2xl font-bold text-gray-800">{{ title }}</div>
		<div class="flex flex-col space-y-2">
			<AvatarCard
				v-for="card in cards"
				class="cursor-pointer"
				:key="card[rowKey as keyof AvatarCardProps]"
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
import AvatarCard from "@/components/AppLayout/AvatarCard.vue"
import type { AvatarCardProps } from "@/types/studio_components/AvatarCard"
import type { CardListProps, CardListEmits } from "@/types/studio_components/CardList"

const emit = defineEmits<CardListEmits>()
withDefaults(defineProps<CardListProps>(), {
	cards: () => [],
	rowKey: "name",
})

const selectedCard = ref<AvatarCardProps | null>(null)
defineExpose({
	selectedCard,
})
</script>
