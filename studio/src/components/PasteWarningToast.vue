<template>
	<div class="flex w-[360px] items-start gap-2 rounded-md bg-surface-gray-9 px-4 py-3 shadow-xl">
		<div class="min-w-0 flex-1">
			<p class="text-p-base font-medium text-ink-base">Page script wasn't copied</p>
			<p class="mt-0.5 text-p-base leading-5 text-ink-base">
				These blocks may use page-level functions or variables from the source page. Add required references
				from the source manually or revert the pasted blocks.
			</p>
			<button
				type="button"
				class="-ml-2 mt-1.5 rounded px-2 py-1 text-base font-medium text-ink-blue-link hover:bg-surface-gray-8"
				@click="revertPaste"
			>
				Revert pasted blocks
			</button>
		</div>
		<button
			type="button"
			class="grid size-5 shrink-0 place-items-center rounded-sm text-ink-base hover:bg-surface-gray-8"
			aria-label="Close notification"
			@click="onCloseToast"
		>
			<span class="lucide-x size-4" />
		</button>
	</div>
</template>

<script setup lang="ts">
const props = defineProps<{
	onRevert: () => void
	onCloseToast: () => void
}>()

function revertPaste() {
	props.onRevert()
	props.onCloseToast()
}
</script>
