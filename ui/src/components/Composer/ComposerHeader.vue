<template>
	<div class="flex items-center justify-between gap-2 py-1.5">
		<!-- Static channel label ("Via Email" / "Via Comment"). Each composer is
			 single-channel, so there's no switcher. -->
		<div class="flex items-center gap-[5px] text-p-sm text-ink-gray-5">
			<span>Via</span>
			<span class="font-medium text-ink-gray-8">{{ title }}</span>
		</div>

		<!-- Channel-specific controls (e.g. the email field toggles). Window
			 controls (dock / pop-out) belong to the host's FloatingWindow. -->
		<div class="flex items-center gap-1">
			<slot name="actions" />
		</div>
	</div>
</template>

<script setup lang="ts">
defineProps<{
	/** Channel label shown after "Via" (e.g. "Email", "Comment"). */
	title: string;
}>();
</script>
