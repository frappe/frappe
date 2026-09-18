<!-- The panel column's content: `page.panelSections` as one list, or the quick actions as
     icons when the reader shut the column to a strip. -->
<template>
	<div class="flex min-h-full flex-col" data-record-panel>
		<!-- A script that hid `quick_actions` leaves the strip with the expand control alone. -->
		<div v-if="collapsed" class="flex flex-col items-center py-3">
			<QuickActions v-if="controller.panelSections.isVisible('quick_actions')" vertical />
		</div>

		<PanelLayout
			v-else
			v-model:doc="doc"
			:surface="controller.panelSections"
			:sections="sections"
			:page="controller.page"
			:isOpen="disclosure.isOpen"
			@toggle="disclosure.toggle"
			@expand="emit('expand', $event)"
		/>
	</div>
</template>

<script setup lang="ts">
import { provide, toRef } from "vue";
import type { FieldNode } from "@framework/ui/components/FormLayout/types";
import type { QuickAction, RecordPageController } from "@/recordPage";
import { PanelContextKey, type DocInfo } from "./context";
import type { Disclosure } from "./disclosure";
import PanelLayout from "./PanelLayout.vue";
import type { LayoutSection } from "./panelEntries";
import QuickActions from "./QuickActions.vue";

const props = defineProps<{
	doctype: string;
	docname: string;
	controller: RecordPageController;
	meta: any;
	docinfo: DocInfo | null;
	sections: LayoutSection[];
	disclosure: Disclosure;
	collapsed: boolean;
	run: (action: QuickAction) => void;
	reloadDocinfo: () => Promise<void>;
	whileOnRecord: () => () => boolean;
}>();

const emit = defineEmits<{ expand: [field: FieldNode] }>();

const doc = defineModel<Record<string, any>>("doc", { required: true });

provide(PanelContextKey, {
	doctype: props.doctype,
	docname: props.docname,
	doc,
	meta: toRef(props, "meta"),
	docinfo: toRef(props, "docinfo"),
	controller: props.controller,
	run: props.run,
	reloadDocinfo: props.reloadDocinfo,
	whileOnRecord: props.whileOnRecord,
});
</script>
