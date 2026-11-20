// a restart of the bench's servers is over well within this
export const RESTART = 10_000;

const FIRST_WAIT = 500;
const LONGEST_WAIT = 4000;

// Runs `request` until it succeeds, waiting longer after each failure. It gives up with the
// request's own error once `retriable(error)` says no, or `within` ms of failures have passed.
export async function retrying(request, { retriable, within }) {
	const deadline = Date.now() + within;
	for (let wait = FIRST_WAIT; ; wait = Math.min(wait * 2, LONGEST_WAIT)) {
		try {
			return await request();
		} catch (error) {
			if (!retriable(error) || Date.now() + wait > deadline) throw error;
		}
		await new Promise((resolve) => setTimeout(resolve, wait));
	}
}
