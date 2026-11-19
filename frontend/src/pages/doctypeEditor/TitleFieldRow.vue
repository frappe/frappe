<!-- The panel's Title field switch: the DocType's `title_field`, which Settings › Form sets too.
     It stages as a Settings edit, so it joins the header's Save and the one undo stack. -->
<template>
	<PanelRow :label="__('Title field')" :box="false">
		<div class="flex min-h-7 flex-col justify-center px-2">
			<div class="flex h-7 items-center">
				<Switch
					size="sm"
					:model-value="isTitle"
					data-panel-title-field
					@update:model-value="set($event)"
				/>
			</div>
			<p v-if="isTitle" class="pb-1 text-p-sm text-ink-gray-5" data-panel-title-hint>
				{{ __("Lists and links show this instead of the ID.") }}
			</p>
		</div>
	</PanelRow>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { Switch } from "frappe-ui";
import type { RawMetaField } from "@framework/ui/FormLayout/types";
import { acts } from "@/acts/dispatcher";
import { __ } from "@/i18n";
import type { DesignCanvas } from "./designCanvas";
import PanelRow from "./PanelRow.vue";

const props = defineProps<{ canvas: DesignCanvas; field: RawMetaField }>();

const isTitle = computed(
	() => props.canvas.working.value.settings.properties.title_field === props.field.fieldname
);

function set(on: boolean) {
	void acts.perform("settings.set_doctype_property", {
		property: "title_field",
		value: on ? props.field.fieldname : "",
	});
}
</script>
