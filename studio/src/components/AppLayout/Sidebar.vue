<template>
	<div class="flex h-full min-h-screen w-60 grow flex-col overflow-auto bg-gray-50 px-2 pt-2">
		<nav class="mt-4 flex flex-col space-y-1">
			<div class="w-full" v-for="item in items" :key="item.label">
				<component
					:is="item.route_to ? 'router-link' : 'div'"
					:to="item.route_to"
					class="flex cursor-pointer items-center gap-2 truncate rounded px-2 py-1 transition duration-300 ease-in-out"
					:class="[item.selected ? 'bg-white shadow-sm' : 'hover:bg-gray-200']"
				>
					<FeatherIcon :name="item.featherIcon || 'folder-normal'" class="h-5 w-5 text-gray-700" />
					<div class="flex items-center gap-1 truncate text-base text-gray-700">
						{{ item.label }}
					</div>
				</component>
			</div>
		</nav>
	</div>
</template>

<script setup>
defineProps({
	items: {
		type: Array,
		required: true,
	},
})
</script>
