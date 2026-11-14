<!-- "New child table…": the new child DocType's name, prefilled from the parent and the table's
     label, and for a Table MultiSelect the DocType its one Link field names. Nothing is written
     here: the parent's next save inserts it first. -->
<template>
	<Dialog
		v-model:open="isOpen"
		:title="__('New child table')"
		@update:open="!$event && emit('cancel')"
	>
		<div class="flex flex-col gap-4" data-new-child-dialog>
			<FormControl
				v-model="name"
				:label="__('Name')"
				:error="nameError"
				:description="__('A child DocType in {0}, saved with {1}.', [module, parent])"
				autofocus
			/>
			<Combobox
				v-if="multiselect"
				v-model="link"
				:label="__('Links to')"
				:options="doctypes"
				:placeholder="__('Choose a DocType')"
				data-new-child-link
			/>
		</div>
		<template #actions>
			<div class="flex justify-end gap-2">
				<Button :label="__('Cancel')" @click="emit('cancel')" />
				<Button
					variant="solid"
					:label="__('Create')"
					:disabled="!name.trim() || (multiselect && !link)"
					:loading="checking"
					@click="create"
				/>
			</div>
		</template>
	</Dialog>
</template>

<script setup lang="ts">
import { computed, inject, ref } from "vue";
import { Button, Combobox, Dialog, FormControl, toast } from "frappe-ui";
import { listDocuments } from "@framework/ui/api";
import type { Addresses } from "@/addresses";
import { __ } from "@/i18n";
import { errorMessage } from "@/recordPage/errorMessage";
import { newChildName } from "./childSource";

const props = defineProps<{
	parent: string;
	module: string;
	label: string;
	/** The new child tables this save already makes. */
	staged: string[];
	/** A Table MultiSelect's child: it holds one Link field, so the dialog asks where it links. */
	multiselect?: boolean;
}>();
const emit = defineEmits<{ create: [name: string, link?: string]; cancel: [] }>();

const doctypes = inject<Addresses>("addresses")!.doctypes();
const link = ref<string | null>(null);

const isOpen = ref(true);
const name = ref(newChildName(props.parent, props.label));
const taken = ref("");
const checking = ref(false);

const nameError = computed(() => {
	const wanted = name.value.trim();
	if (props.staged.includes(wanted))
		return __("A new child table named {0} waits for the save", [wanted]);
	return taken.value && taken.value === wanted
		? __("A DocType named {0} exists already", [taken.value])
		: undefined;
});

async function create() {
	const wanted = name.value.trim();
	if (props.staged.includes(wanted)) return;
	checking.value = true;
	try {
		const { data } = await listDocuments("DocType", {
			fields: ["name"],
			filters: { name: wanted },
			limit: 1,
		});
		taken.value = data.length ? wanted : "";
	} catch (error) {
		return void toast.error(errorMessage(error));
	} finally {
		checking.value = false;
	}
	if (!taken.value) emit("create", wanted, link.value ?? undefined);
}
</script>
