// The page layer's component that draws a settings pane's blocks, which `main.ts` registers.
import { markRaw, type Component } from "vue";

type BlocksLoader = () => Promise<{ default: Component }>;

let blocksLoader: BlocksLoader | null = null;

/** `main.ts` registers the page layer's component that draws a pane's blocks; it takes `pane` and emits `loaded`. */
export function registerSettingsBlocks(loader: BlocksLoader) {
	blocksLoader = loader;
}

export async function loadSettingsBlocks(): Promise<Component> {
	if (!blocksLoader) throw new Error("The settings dialog opened before its blocks were registered");
	return markRaw((await blocksLoader()).default);
}
