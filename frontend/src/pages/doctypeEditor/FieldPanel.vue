<!-- The selected field's settings, in the look of frappe/crm#3419's PanelFieldSettings. Each change
     stages an edit at once; a text property stages when it is left or Enter is pressed. -->
<template>
	<PanelHeader
		:icon="typeIcon(currentType)"
		:title="field.label || field.fieldname"
		:subtitle="subtitle(canvas, field)"
		:remove-label="removal.label"
		:remove-icon="removal.icon"
		:remove-active="removal.icon === 'lucide-eye'"
		@remove="remove"
		@close="acts.perform('canvas.select', null)"
	/>
	<div v-if="errors.length || warning" class="flex flex-col gap-2 px-4 pb-3">
		<p v-for="error in errors" :key="error" class="text-p-sm text-ink-red-4" data-panel-error>
			{{ error }}
		</p>
		<Alert
			v-if="warning"
			theme="amber"
			:title="__('Mandatory in a conditional container')"
			:description="warning"
			data-panel-reqd-warning
		/>
	</div>
	<PanelSection :label="__('Field')">
		<PanelRow :label="__('Label')" v-bind="mark('label')">
			<TextInput
				variant="ghost"
				:model-value="field.label ?? ''"
				:placeholder="field.fieldname"
				data-panel-label
				@change="set('label', text($event))"
			/>
		</PanelRow>
		<PanelRow :label="__('Type')" :box="false" v-bind="mark('fieldtype')">
			<div class="rounded-4 hover:bg-surface-gray-2">
				<Dropdown :options="typeMenu" side="bottom" align="start">
					<button
						type="button"
						class="flex h-7 w-full items-center gap-2 rounded-4 px-2 text-left text-base text-ink-gray-8"
						data-panel-type
					>
						<span
							:class="[typeIcon(currentType), 'size-4 shrink-0 text-ink-gray-5']"
							aria-hidden="true"
						/>
						<span class="min-w-0 flex-1 truncate">{{ __(currentType) }}</span>
						<span
							class="lucide-chevron-down size-4 shrink-0 text-ink-gray-5"
							aria-hidden="true"
						/>
					</button>
				</Dropdown>
			</div>
			<p v-if="note" class="px-2 pb-1 pt-0.5 text-p-sm text-ink-gray-5" data-panel-type-note>
				{{ note }}
			</p>
		</PanelRow>
		<PanelRow v-if="anchor !== undefined" :label="__('Placed after')" :box="false">
			<div class="flex min-h-7 flex-col justify-center px-2" data-panel-anchor>
				<p class="flex h-7 items-center text-base text-ink-gray-8">
					<span class="min-w-0 truncate">{{
						anchor ? anchor.label || anchor.fieldname : __("The start of the form")
					}}</span>
				</p>
				<p class="pb-1 text-p-sm text-ink-gray-5">
					<template v-if="anchor"
						><code class="font-mono">{{ anchor.fieldname }}</code
						>.
					</template>
					{{
						__("Drag it to move it. It keeps this place when {0} adds fields.", [
							appTitle,
						])
					}}
				</p>
			</div>
		</PanelRow>
		<FieldTabRow
			v-if="canvas.tabs.value.length > 1 && canvas.place(field.fieldname)"
			:canvas="canvas"
			:field="field"
		/>
		<PanelRow
			v-if="field.fieldtype === 'Link'"
			:label="__('Links to')"
			v-bind="mark('options')"
		>
			<Combobox
				variant="ghost"
				class="w-full min-w-0 border-0"
				:model-value="field.options ?? ''"
				:options="doctypes"
				:placeholder="__('Choose a DocType')"
				@update:model-value="setTarget(String($event ?? ''))"
			/>
		</PanelRow>
		<TableFieldRows
			v-else-if="TABLE_TYPES.includes(field.fieldtype)"
			:canvas="canvas"
			:field="field"
		/>
		<PanelRow
			v-else-if="field.fieldtype === 'Select'"
			:label="__('Options')"
			v-bind="mark('options')"
		>
			<Textarea
				variant="ghost"
				:rows="3"
				class="!resize-none [textarea&]:text-base"
				:placeholder="__('One per line')"
				:model-value="field.options ?? ''"
				@change="set('options', text($event))"
			/>
		</PanelRow>
		<PanelRow
			v-else-if="field.fieldtype === 'Dynamic Link'"
			:label="__('DocType from')"
			v-bind="mark('options')"
		>
			<TextInput
				variant="ghost"
				:model-value="field.options ?? ''"
				:placeholder="__('A Link field to DocType')"
				@change="set('options', text($event))"
			/>
		</PanelRow>
		<LinkFiltersRow
			v-if="field.fieldtype === 'Link' && field.options"
			:key="field.options"
			:canvas="canvas"
			:field="field"
			v-bind="mark('link_filters')"
		/>
		<FetchedRow
			v-if="field.fieldtype === 'Link' && field.options"
			:canvas="canvas"
			:field="field"
		/>
		<PanelRow :label="__('Required')" :box="false" v-bind="mark('reqd')">
			<div class="flex h-7 items-center px-2">
				<Switch
					size="sm"
					:model-value="Boolean(field.reqd)"
					@update:model-value="set('reqd', $event ? 1 : 0)"
				/>
			</div>
		</PanelRow>
		<TitleFieldRow v-if="titleable" :canvas="canvas" :field="field" />
		<PanelRow
			v-if="!TABLE_TYPES.includes(field.fieldtype)"
			:label="__('Default')"
			v-bind="mark('default')"
		>
			<TextInput
				variant="ghost"
				:model-value="field.default ?? ''"
				:placeholder="__('None')"
				@change="set('default', text($event))"
			/>
		</PanelRow>
		<PanelRow
			v-if="fetchable(field)"
			:label="__('Fetch from')"
			:box="false"
			v-bind="mark('fetch_from')"
		>
			<FetchFromRow :canvas="canvas" :field="field" />
		</PanelRow>
		<PanelRow
			v-if="field.fetch_from"
			:label="__('Only when empty')"
			:box="false"
			v-bind="mark('fetch_if_empty')"
		>
			<div class="flex h-7 items-center px-2">
				<Switch
					size="sm"
					:model-value="Boolean(field.fetch_if_empty)"
					data-panel-fetch-if-empty
					@update:model-value="set('fetch_if_empty', $event ? 1 : 0)"
				/>
			</div>
			<p class="px-2 pb-1 text-p-sm text-ink-gray-5" data-panel-fetch-hint>
				{{
					field.fetch_if_empty
						? __("Copies from {0} only while this field is empty.", [
								fetchSource || __("the link"),
						  ])
						: __("Copies from {0} on every save; a typed value is replaced.", [
								fetchSource || __("the link"),
						  ])
				}}
			</p>
		</PanelRow>
		<PanelRow
			v-if="field.fieldtype !== 'Check' && !TABLE_TYPES.includes(field.fieldtype)"
			:label="__('Placeholder')"
			v-bind="mark('placeholder')"
		>
			<TextInput
				variant="ghost"
				:model-value="field.placeholder ?? ''"
				:placeholder="__('Add placeholder…')"
				@change="set('placeholder', text($event))"
			/>
		</PanelRow>
		<PanelRow :label="__('Help text')" v-bind="mark('description')">
			<Textarea
				variant="ghost"
				:rows="1"
				class="!min-h-7 !resize-none !py-1 [textarea&]:text-base"
				:model-value="field.description ?? ''"
				:placeholder="__('Add help text…')"
				@change="set('description', text($event))"
			/>
		</PanelRow>
		<FieldnameRow :canvas="canvas" :field="field" />
	</PanelSection>
	<FieldRules :canvas="canvas" :field="field" />
	<FieldPropertyGroups :canvas="canvas" :field="field" />
</template>

<script setup lang="ts">
import { computed, inject } from "vue";
import { Alert, Combobox, Dropdown, Switch, Textarea, TextInput } from "frappe-ui";
import type { RawMetaField } from "@framework/ui/FormLayout/types";
import { acts } from "@/acts/dispatcher";
import type { Addresses } from "@/addresses";
import { __ } from "@/i18n";
import type { DesignCanvas } from "./designCanvas";
import FetchedRow from "./FetchedRow.vue";
import { fetchable } from "./fetchFrom";
import FetchFromRow from "./FetchFromRow.vue";
import FieldTabRow from "./FieldTabRow.vue";
import FieldnameRow from "./FieldnameRow.vue";
import {
	removeAction,
	reqdWarning,
	panelMark,
	subtitle,
	removeField,
	typeChange,
	typeMenuOptions,
	typeNote,
} from "./fieldPanel";
import FieldPropertyGroups from "./FieldPropertyGroups.vue";
import FieldRules from "./FieldRules.vue";
import { TABLE_TYPES, typeIcon, typeName } from "./fieldtypes";
import LinkFiltersRow from "./LinkFiltersRow.vue";
import { targetChange } from "./linkFilters";
import { settable } from "./settingsModel";
import { kindOf, MANY, TITLE_TYPES } from "./settingsRows";
import PanelHeader from "./PanelHeader.vue";
import { providePanelIndex } from "./panelIndex";
import PanelRow from "./PanelRow.vue";
import PanelSection from "./PanelSection.vue";
import TitleFieldRow from "./TitleFieldRow.vue";
import TableFieldRows from "./TableFieldRows.vue";

const props = defineProps<{ canvas: DesignCanvas; field: RawMetaField }>();
providePanelIndex();

const doctypes = inject<Addresses>("addresses")!.doctypes();
const currentType = computed(() => typeName(props.field.fieldtype, props.field.options));
const note = computed(() => typeNote(props.canvas, props.field));
const errors = computed(() => props.canvas.errorsAt("field", props.field.fieldname));
const warning = computed(() => reqdWarning(props.canvas, props.field.fieldname));
const removal = computed(() => removeAction(props.canvas, props.field));
const anchor = computed(() => props.canvas.customize?.anchor(props.field.fieldname));
const fetchSource = computed(() => {
	const link = props.field.fetch_from?.split(".")[0] ?? "";
	return props.canvas.field(link)?.options ?? "";
});
const titleable = computed(() => {
	const { settings } = props.canvas.working.value;
	return (
		settable(settings, "title_field") &&
		MANY.includes(kindOf(settings.properties)) &&
		TITLE_TYPES.includes(props.field.fieldtype)
	);
});
const appTitle = computed(() => props.canvas.state.app_title || __("the app"));

const typeMenu = computed(() => typeMenuOptions(props.canvas, props.field.fieldname, pickType));

function set(property: string, value: unknown) {
	const current = (props.field as unknown as Record<string, unknown>)[property] ?? "";
	if (value === current) return;
	void acts.perform("fields.set_field_property", {
		fieldname: props.field.fieldname,
		property,
		value,
	});
}

function setTarget(doctype: string) {
	if (doctype === (props.field.options ?? "")) return;
	void acts.perform("fields.set_field_property", {
		fieldname: props.field.fieldname,
		properties: targetChange(props.field, doctype),
	});
}

function mark(property: string) {
	return panelMark(props.canvas, props.field.fieldname, property);
}

function pickType(name: string) {
	if (name === currentType.value) return;
	void acts.perform("fields.set_field_property", {
		fieldname: props.field.fieldname,
		properties: typeChange(props.field, name),
	});
}

function remove() {
	return removeField(props.canvas, props.field);
}

function text(event: Event) {
	return (event.target as HTMLInputElement).value.trim();
}
</script>
