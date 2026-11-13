<!-- The field's rarer plain properties, in closed groups that count what is set. -->
<template>
	<PanelSection
		v-for="group in groups"
		:key="group.label"
		:label="__(group.label)"
		:start-open="false"
		:count="group.set"
	>
		<PanelRow
			v-for="property in group.properties"
			:key="property.key"
			:label="__(property.label)"
			:box="property.type !== 'check'"
			v-bind="mark(property.key)"
		>
			<div v-if="property.type === 'check'" class="flex h-7 items-center px-2">
				<Switch
					size="sm"
					:model-value="Boolean(value(property.key))"
					@update:model-value="set(property.key, $event ? 1 : 0)"
				/>
			</div>
			<TextInput
				v-else
				variant="ghost"
				type="number"
				:placeholder="property.placeholder ?? __('None')"
				:model-value="value(property.key) ?? ''"
				@change="
					set(property.key, numberOrNull(($event.target as HTMLInputElement).value))
				"
			/>
		</PanelRow>
	</PanelSection>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { Switch, TextInput } from "frappe-ui";
import type { RawMetaField } from "@framework/ui/FormLayout/types";
import { acts } from "@/acts/dispatcher";
import { __ } from "@/i18n";
import type { DesignCanvas } from "./designCanvas";
import { PROPERTY_GROUPS, rowMark } from "./fieldPanel";
import PanelRow from "./PanelRow.vue";
import PanelSection from "./PanelSection.vue";

const props = defineProps<{ canvas: DesignCanvas; field: RawMetaField }>();

const groups = computed(() =>
	PROPERTY_GROUPS.map((group) => {
		const properties = group.properties.filter(
			(property) => !property.only || property.only(props.field, props.canvas)
		);
		return { ...group, properties, set: properties.filter((one) => value(one.key)).length };
	})
);

function value(key: string) {
	return (props.field as unknown as Record<string, unknown>)[key] as string | number | undefined;
}

function mark(property: string) {
	const { fieldname } = props.field;
	return {
		...rowMark(props.canvas, fieldname, property),
		onReset: () => void acts.perform("fields.reset_field_property", { fieldname, property }),
	};
}

function set(key: string, next: number | null) {
	if ((value(key) ?? (next === null ? null : 0)) === next) return;
	void acts.perform("fields.set_field_property", {
		fieldname: props.field.fieldname,
		property: key,
		value: next,
	});
}

// A cleared input unsets the property: 0 is a value (no decimal places), not "the default".
function numberOrNull(text: string) {
	return text.trim() === "" ? null : Number(text);
}
</script>
