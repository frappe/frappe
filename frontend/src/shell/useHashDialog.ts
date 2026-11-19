// A hash dialog addressed by `route.hash`: `#<root>/<segments…>` on whatever page is open, so it
// is linkable and Back dismisses it. One hash, one hash dialog.

import { computed, type ComputedRef } from "vue";
import { useRoute, useRouter, type Router } from "vue-router";

export interface HashDialog {
	/** Whether the current hash is this dialog's. */
	open: ComputedRef<boolean>;
	/** The segments after the root; empty while closed. */
	segments: ComputedRef<string[]>;
	/** Opens the dialog, or moves within it if it is already open; resolves to the router's failure, if any. */
	write: (...segments: string[]) => ReturnType<Router["push"]>;
	/** Drops the hash, leaving the query untouched. */
	close: () => void;
}

export function useHashDialog(root: string): HashDialog {
	const route = useRoute();
	const router = useRouter();

	// Raw segments: the router percent-encodes the hash on the way in and decodes it on the way out.
	const ours = computed(() => {
		const [head, ...rest] = route.hash.replace(/^#/, "").split("/");
		return head === root ? rest : null;
	});

	const open = computed(() => ours.value !== null);
	const segments = computed(() => ours.value ?? []);

	// Push to open, replace within: opening is the navigation Back should undo.
	function write(...path: string[]) {
		const to = { query: route.query, hash: `#${[root, ...path].join("/")}` };
		return open.value ? router.replace(to) : router.push(to);
	}

	// Only ever our own hash is dropped; another hash dialog's hash is not ours to throw away.
	function close() {
		if (open.value) router.replace({ query: route.query, hash: "" });
	}

	return { open, segments, write, close };
}
