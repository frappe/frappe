// Rows the page on screen adds to the avatar menu, from mount to unmount.
import { onBeforeUnmount, shallowRef } from "vue";

export type PageMenuItem = { label: string; icon: string; onClick: () => void };

export const pageMenuItems = shallowRef<PageMenuItem[]>([]);

/** Shows `items` in the avatar menu until the calling component unmounts. */
export function usePageMenuItems(items: PageMenuItem[]) {
	pageMenuItems.value = items;
	// The next page's setup runs before this one unmounts, so clear only rows this page set.
	onBeforeUnmount(() => {
		if (pageMenuItems.value === items) pageMenuItems.value = [];
	});
}
