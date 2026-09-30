// The doctype's meta through the shared source, as one promise a load can await or as it is now.
import { watch } from "vue";
import { useDoctypeMeta } from "@framework/ui/composables/useDoctypeMeta";

type Settling = { meta: { value: any }; error: { value: unknown }; refreshing?: { value: boolean } };

/** The fresh meta: a stale one is waited out. */
export function fetchMeta(doctype: string) {
	return awaitMeta(useDoctypeMeta(doctype));
}

/** The meta the shared source already holds, stale or not, or null while it loads or failed. */
export function metaInMemory(doctype: string): any {
	return useDoctypeMeta(doctype).meta.value;
}

/** Answers now when the source already holds a fresh meta; a watcher created with `immediate` would fire before its stop handle exists. */
export function awaitMeta(source: Settling): Promise<any> {
	const settled = () => !source.refreshing?.value && (source.meta.value ?? source.error.value);
	if (settled()) return source.meta.value ? Promise.resolve(source.meta.value) : Promise.reject(source.error.value);
	return new Promise((resolve, reject) => {
		const stop = watch(settled, (done) => {
			if (!done) return;
			stop();
			if (source.meta.value) resolve(source.meta.value);
			else reject(source.error.value);
		});
	});
}
