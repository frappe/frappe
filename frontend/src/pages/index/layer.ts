// The person's own layer over the index's tiles: their order and the apps they hid.
import { runMethod } from "@framework/ui/api";
import type { IndexApp } from "./apps";

/** Stores the order and hidden apps these tiles show, and returns the tiles as boot would now list them. */
export async function saveLayer(apps: IndexApp[]): Promise<IndexApp[]> {
	const response = await runMethod<IndexApp[]>("frappe.shell.boot.save_index_layer", {
		order: apps.map((app) => app.app),
		hidden: apps.filter((app) => app.hidden).map((app) => app.app),
	});
	return response.data;
}

/** Clears the layer, and returns the tiles in the app layer's order. */
export async function resetLayer(): Promise<IndexApp[]> {
	return saveLayer([]);
}
