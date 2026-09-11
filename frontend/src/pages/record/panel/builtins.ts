// The four items the host seeds, in this order. No label: a built-in draws no header.
import { markRaw } from "vue";
import type { PanelSectionItem } from "@/recordPage";
import QuickActions from "./QuickActions.vue";
import RecordAssignees from "./RecordAssignees.vue";
import RecordIdentity from "./RecordIdentity.vue";
import RecordShares from "./RecordShares.vue";

export const PANEL_BUILTINS: PanelSectionItem[] = [
	{ name: "identity", component: markRaw(RecordIdentity) },
	{ name: "quick_actions", component: markRaw(QuickActions) },
	{ name: "assignees", component: markRaw(RecordAssignees) },
	{ name: "shares", component: markRaw(RecordShares) },
];
