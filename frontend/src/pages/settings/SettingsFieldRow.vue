<!-- One field as a settings row: the ui control on the right, a Check as a switch, a long field's
     control under its title. A refused value keeps the server's message under the row. -->
<template>
	<div
		:data-fieldname="field.fieldname"
		class="relative border-b border-outline-gray-1 last:border-b-0"
	>
		<span data-flash aria-hidden="true" :class="FLASH" />
		<div v-if="isLong(field)" class="py-3.5">
			<div class="flex items-start gap-2">
				<div class="min-w-0 flex-1">
					<div class="text-base-medium leading-tighter text-ink-gray-8">{{ title }}</div>
					<div v-if="description" class="mt-1 text-base leading-5 text-ink-gray-6">
						{{ description }}
					</div>
				</div>
				<SettingsSaveMark :mark="mark" />
			</div>
			<component
				:is="control"
				class="mt-2"
				:field="bare"
				:modelValue="value"
				@update:modelValue="edit"
				@change="emit('commit')"
			/>
		</div>
		<SettingsRow v-else :title="title" :description="description">
			<div class="flex items-center gap-2">
				<SettingsSaveMark :mark="mark" />
				<Switch
					v-if="field.fieldtype === 'Check'"
					:model-value="!!value"
					:disabled="field.readOnly"
					@update:model-value="toggle"
				/>
				<component
					:is="control"
					v-else
					class="w-56"
					:field="bare"
					:modelValue="value"
					@update:modelValue="edit"
					@change="emit('commit')"
				/>
			</div>
		</SettingsRow>
		<ErrorMessage v-if="message" class="-mt-1.5 pb-3.5" :message="message" />
	</div>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { ErrorMessage, SettingsRow, Switch } from "frappe-ui";
import { getFieldComponent } from "@framework/ui/FormLayout";
import { fieldnameOfErrorKey } from "@framework/ui/fields/types";
import type { FieldNode } from "@framework/ui/FormLayout/types";
import { __ } from "@/i18n";
import type { BindingDraft } from "./bindingDraft";
import { isLong } from "./settingsRows";
import SettingsSaveMark from "./SettingsSaveMark.vue";

const props = defineProps<{ field: FieldNode; draft: BindingDraft }>();
const emit = defineEmits<{ commit: [] }>();

/** A rounded gray layer a little wider than the row, clear of its dividers, behind the block's content. */
const FLASH =
	"pointer-events-none absolute -inset-x-3 inset-y-1 -z-10 rounded-4 bg-surface-gray-3 opacity-0";

const title = computed(() => __(props.field.label || props.field.fieldname));
const description = computed(() => props.field.description && __(props.field.description));
const control = computed(() => getFieldComponent(props.field.fieldtype));
const bare = computed(() => ({ ...props.field, label: "", description: "" }));
const value = computed(() => props.draft.state.doc[props.field.fieldname]);
const mark = computed(() => props.draft.state.marks[props.field.fieldname]);

/** The field's own message, or its first row cell's for a table. */
const message = computed(() => {
	const drawn = props.draft.fieldErrors.drawn.value;
	const key = Object.keys(drawn).find(
		(one) => fieldnameOfErrorKey(one) === props.field.fieldname
	);
	return drawn[props.field.fieldname] ?? (key ? drawn[key] : undefined);
});

function edit(next: unknown) {
	props.draft.edit(props.field.fieldname, next);
}

function toggle(on: boolean) {
	edit(on ? 1 : 0);
	emit("commit");
}
</script>
