<!-- The record's right-hand column: `page.panelSections` as one list, resizable, and
     collapsible to a strip that keeps the quick actions as icons. -->
<template>
	<PanelEdge
		v-model:width="width"
		v-model:dragging="dragging"
		:open="!collapsed"
		@toggle="collapsed = !collapsed"
	/>

	<aside
		class="flex shrink-0 flex-col overflow-hidden border-l border-outline-gray-1"
		:class="dragging ? '' : 'transition-[width] duration-300 ease-in-out'"
		:style="{ width: `${collapsed ? STRIP_WIDTH : width}px` }"
		data-record-panel
	>
		<!-- A script that hid `quick_actions` leaves the strip with the expand control alone. -->
		<div v-if="collapsed" class="flex flex-col items-center py-3">
			<QuickActions v-if="controller.panelSections.isVisible('quick_actions')" vertical />
		</div>

		<div v-else class="min-h-0 flex-1 overflow-y-auto" :style="{ width: `${width}px` }">
			<PanelLayout
				v-model:doc="doc"
				:surface="controller.panelSections"
				:sections="sections"
				:page="controller.page"
				:isOpen="disclosure.isOpen"
				@toggle="disclosure.toggle"
				@expand="emit('expand', $event)"
			/>
		</div>
	</aside>
</template>

<script setup lang="ts">
import { provide, ref, toRef } from "vue";
import type { FieldNode } from "@framework/ui/components/FormLayout/types";
import type { QuickAction, RecordPageController } from "@/recordPage";
import { PanelContextKey, type DocInfo } from "./context";
import type { Disclosure } from "./disclosure";
import { STRIP_WIDTH, usePanelGeometry } from "./geometry";
import PanelEdge from "./PanelEdge.vue";
import PanelLayout from "./PanelLayout.vue";
import type { LayoutSection } from "./panelEntries";
import QuickActions from "./QuickActions.vue";

const props = defineProps<{
	user: string;
	doctype: string;
	docname: string;
	controller: RecordPageController;
	meta: any;
	docinfo: DocInfo | null;
	sections: LayoutSection[];
	disclosure: Disclosure;
	run: (action: QuickAction) => void;
}>();

const emit = defineEmits<{ expand: [field: FieldNode] }>();

const doc = defineModel<Record<string, any>>("doc", { required: true });

const { width, collapsed } = usePanelGeometry(props.user);
const dragging = ref(false);

provide(PanelContextKey, {
	doctype: props.doctype,
	docname: props.docname,
	doc,
	meta: toRef(props, "meta"),
	docinfo: toRef(props, "docinfo"),
	controller: props.controller,
	run: props.run,
});
</script>
