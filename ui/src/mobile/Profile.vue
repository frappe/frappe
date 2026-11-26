<template>
	<div data-slot="profile" class="h-full overflow-y-auto bg-surface-gray-1">
		<div class="space-y-6 px-4 pt-3 pb-10">
			<header
				v-if="$slots.header"
				data-slot="profile-header"
				class="flex flex-col items-center pt-5 pb-2 text-center"
			>
				<slot name="header" />
			</header>
			<slot />
		</div>
	</div>
</template>
