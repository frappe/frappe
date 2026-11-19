// Stands for the record page in a composer test: it holds the page's writer context while mounted.
import { defineComponent, inject } from "vue";
import type { RecordPageController } from "@/recordPage";
import { RecordFeedsKey } from "../../feed/recordFeeds";
import { useComposerRecord } from "../writerContext";

export const RecordPageStub = defineComponent({
	props: { controller: { type: Object, required: true } },
	setup(props, { slots }) {
		const feeds = inject(RecordFeedsKey, null);
		useComposerRecord(() => props.controller as RecordPageController, feeds);
		return () => slots.default?.();
	},
});
