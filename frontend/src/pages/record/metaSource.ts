// The doctype's meta through the shared source, as one promise a load can await.
import { watch } from "vue";
import { useDoctypeMeta } from "@framework/ui/composables/useDoctypeMeta";

type Settling = { meta: { value: any }; error: { value: unknown } };

export function fetchMeta(doctype: string) {
	return awaitMeta(useDoctypeMeta(doctype));
}

/** Answers now when the source already holds the meta; a watcher created with `immediate` would fire before its stop handle exists. */
export function awaitMeta(source: Settling): Promise<any> {
	if (source.meta.value) return Promise.resolve(source.meta.value);
	if (source.error.value) return Promise.reject(source.error.value);
	return new Promise((resolve, reject) => {
		const stop = watch(
			() => source.meta.value ?? source.error.value,
			(settled) => {
				if (!settled) return;
				stop();
				if (source.meta.value) resolve(source.meta.value);
				else reject(source.error.value);
			}
		);
	});
}
