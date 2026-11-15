// A Danger zone dialog's Confirm: it sends the act's call, and a failure stays in the dialog.
import { ref } from "vue";
import { errorMessage } from "@/recordPage/errorMessage";

export function useDangerSubmit<V, R>(submit: (value: V) => Promise<R>, close: (result: R) => void) {
	const working = ref(false);
	const error = ref("");

	async function send(value: V) {
		if (working.value) return;
		working.value = true;
		error.value = "";
		try {
			close(await submit(value));
		} catch (exception) {
			error.value = errorMessage(exception);
		} finally {
			working.value = false;
		}
	}

	return { working, error, send };
}
