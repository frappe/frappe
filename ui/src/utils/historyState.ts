// One key of the history entry's state, written over vue-router's keys. A browser refuses writes
// past a rate, and a refusal here must not stop the page.

/** False, with a warning, when the browser refuses the write. */
export function keepInHistory(key: string, value: unknown): boolean {
	try {
		history.replaceState({ ...history.state, [key]: value }, "");
		return true;
	} catch (error) {
		console.warn(`[history] ${key} was not kept in the history entry`, error);
		return false;
	}
}
