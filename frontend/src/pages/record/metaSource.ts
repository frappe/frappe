// The doctype's meta through the shared source, as one promise a load can await or as it is now.
import { watch } from "vue";
import { useDoctypeMeta } from "@framework/ui/useDoctypeMeta";

type Settling = {
	meta: { value: any };
	error: { value: unknown };
	loading?: { value: boolean };
	refreshing?: { value: boolean };
	refreshError?: { value: unknown };
};

/** The fresh meta: a stale one is waited out, a failed read is read again, and a failed fresh read rejects. */
export function fetchMeta(doctype: string) {
	const source = useDoctypeMeta(doctype);
	if (source.error.value && !source.loading.value) source.reload();
	return awaitMeta(source);
}

/** The meta the shared source already holds, stale or not, or null while it loads or failed. */
export function metaInMemory(doctype: string): any {
	return useDoctypeMeta(doctype).meta.value;
}

/** Answers now when the source already holds a fresh meta; a watcher created with `immediate` would fire before its stop handle exists. */
export function awaitMeta(source: Settling): Promise<any> {
	// A reload keeps the last error until its answer lands.
	const settled = () =>
		!source.loading?.value &&
		!source.refreshing?.value &&
		(source.meta.value ?? source.error.value);
	return new Promise((resolve, reject) => {
		const answer = () => {
			const failure = source.refreshError?.value ?? source.error.value;
			if (failure || !source.meta.value) reject(failure);
			else resolve(source.meta.value);
		};
		if (settled()) return answer();
		const stop = watch(settled, (done) => {
			if (!done) return;
			stop();
			answer();
		});
	});
}
