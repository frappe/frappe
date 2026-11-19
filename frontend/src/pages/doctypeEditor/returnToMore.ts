import { onBeforeUnmount } from "vue";

/** A dialog the header's ⋯ menu opened gives focus back to ⋯ when it closes: the menu item that opened it is gone. */
export function returnToMore() {
	onBeforeUnmount(() => document.querySelector<HTMLElement>("[data-editor-more]")?.focus());
}
