// An act's right on a named doctype: the reader's roles against that doctype's level 0 permission rows.
import { watch, type ComputedRef } from "vue";
import { useDocPermissions } from "@framework/ui/useDocPermissions";

interface DoctypeRight {
	doctype: string;
	ptype: string;
}

export const doctypeRight = {
	passes: ({ doctype, ptype }: DoctypeRight) => useDocPermissions(doctype).holds(ptype),
	/** A promise while that doctype's meta or the roles load, so `passes` cannot answer yet; else nothing. */
	settled: ({ doctype }: DoctypeRight): Promise<void> | undefined => {
		const { loading } = useDocPermissions(doctype);
		return loading.value ? whenLoaded(loading) : undefined;
	},
};

/** Resolves the first time `loading` is false, then disposes its watcher. */
export function whenLoaded(loading: ComputedRef<boolean>): Promise<void> {
	if (!loading.value) return Promise.resolve();
	return new Promise((resolve) => {
		const stop = watch(loading, (still) => {
			if (still) return;
			stop();
			resolve();
		});
	});
}
