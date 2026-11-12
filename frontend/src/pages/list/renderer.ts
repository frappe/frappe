// A view type's renderer as a component, its code loaded once per type, and what the list page
// lends it beside the view.
import { defineAsyncComponent, defineComponent, h, type Component, type Ref } from "vue";
import type { ActEntry } from "@/acts/dispatcher";
import { viewRenderers } from "@/contributions/registry";
import { failedState } from "@/shell/pageState";
import PageState from "@/shell/PageState.vue";
import type { ListPageLists, ListRendererState } from "@/listPage/createListPage";
import type { ListActs } from "./listActs";
import ListView from "./ListView.vue";

export interface RendererHost {
	/** Where the renderer's own controls teleport to, in the controls row; null while it is hidden. */
	controls: Ref<HTMLElement | null>;
	/** Where a renderer with no header row (Cards) teleports its bulk bar, in place of the controls row; null until it mounts. */
	bar: Ref<HTMLElement | null>;
	/** Such a renderer sets it while rows are selected, so the page hides its controls row for the bar. */
	selecting: Ref<boolean>;
	/** The list page's lists: the renderer gives `columns` and `bulkActions` their built-ins and draws them, and `rowActions`. */
	lists: ListPageLists;
	/** Puts the renderer's acts on the acts registry as `<type>.<act>`; `state` is what `page.rows`, `page.selection` and `page.reload` read. */
	acts: (entries: () => ActEntry[], state: ListRendererState) => ListActs;
	/** Runs after the page's Create made a record. */
	onCreate: (callback: () => void) => void;
}

// Imported, not lazy: List stays in the list page's chunk.
const renderers = new Map<string, Component>([["List", ListView]]);

export function rendererFor(type: string): Component {
	let renderer = renderers.get(type);
	if (!renderer) {
		renderer = loaded(type);
		renderers.set(type, renderer);
	}
	return renderer;
}

/** Forgets every loaded renderer; for tests. */
export function clearRenderers() {
	renderers.clear();
	renderers.set("List", ListView);
}

function loaded(type: string): Component {
	const loader = viewRenderers[type];
	if (!loader) return defineComponent(() => () => h(PageState, { name: "notFound" }));
	return defineAsyncComponent({
		loader: loader as () => Promise<Component>,
		errorComponent: defineComponent({
			props: ["error"],
			setup: (props) => () => h(PageState, failedState(props.error, reloadAddress)),
		}),
	});
}

// A full reload: the browser can keep a failed module fetch and fail an in-app retry again.
function reloadAddress() {
	window.location.reload();
}
