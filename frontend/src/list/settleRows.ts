import { watch } from "vue";

const SETTLE_MS = 15000;

/** Resolves once `done` holds, or rejects with the failure then; gives up after SETTLE_MS. */
export function settleRows(done: () => boolean, failure: () => Error | null): Promise<void> {
	const finish = () => {
		const error = failure();
		return error ? Promise.reject(error) : Promise.resolve();
	};
	if (done()) return finish();
	return new Promise((resolve, reject) => {
		const stop = watch(done, (ok) => {
			if (!ok) return;
			stop();
			clearTimeout(limit);
			finish().then(resolve, reject);
		});
		const limit = setTimeout(() => {
			stop();
			reject(new Error("the rows did not load in time"));
		}, SETTLE_MS);
	});
}
