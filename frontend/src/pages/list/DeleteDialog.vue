<!-- The confirmation before a bulk delete; the outcome is toasted, a failure stays in the dialog. -->
<template>
	<Dialog v-model="open" :title="title" size="sm" :actions="actions">
		<template #body-content>
			<p class="text-base text-ink-gray-6">This cannot be undone.</p>
			<p v-if="failure" class="mt-2 text-sm text-ink-red-4">{{ failure }}</p>
		</template>
	</Dialog>
</template>

<script setup lang="ts">
import { Dialog, toast } from "frappe-ui";
import { computed, ref, watch } from "vue";
import type { DeleteOutcome } from "@/list/useListPage";

const props = defineProps<{ count: number; run: () => Promise<DeleteOutcome> }>();
const open = defineModel<boolean>({ default: false });

const deleting = ref(false);
const failure = ref("");
const asked = ref(0);

watch(open, (isOpen) => {
	failure.value = "";
	if (isOpen) asked.value = props.count;
});

const title = computed(() =>
	asked.value === 1 ? "Delete 1 record?" : `Delete ${asked.value} records?`
);

const actions = computed(() =>
	failure.value
		? [{ label: "Close", onClick: () => (open.value = false) }]
		: [
				{
					label: "Delete",
					variant: "solid",
					theme: "red",
					loading: deleting.value,
					onClick: confirm,
				},
		  ]
);

async function confirm() {
	deleting.value = true;
	try {
		report(await props.run());
	} finally {
		deleting.value = false;
	}
}

function report(outcome: DeleteOutcome) {
	if (outcome.deleted.length) toast.success(`Deleted ${outcome.deleted.length} record(s)`);
	if (!outcome.failed.length) {
		open.value = false;
		return;
	}
	failure.value = outcome.failed.map(({ name, error }) => `${name}: ${error}`).join("\n");
}
</script>
