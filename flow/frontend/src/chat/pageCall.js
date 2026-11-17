// The agent's calls to the desk v2 page beside the panel (`list_acts`, `run_act`). The panel shares
// the page's window, so the chat calls `window.desk` directly: no transport of its own. Every
// answer goes back through `screen_result`, as `read_screen`'s does.
const DESK_VERSION = 1;
const DESK_WAIT = 3000; // ms: window.desk appears a moment after the page boots
const ACT_WAIT = 45000; // ms to wait on a confirm; the call itself waits 60 s on the server
// a tab with nothing to drive answers late, so a tab that can drive is heard first: a panel has
// waited for window.desk already, a tab of its own waits out the panels' wait
const LATE_DELAY = 500;
const STANDALONE_DELAY = DESK_WAIT + 500;
const STATE_WAIT = 2000; // ms read_screen gives desk.state()

const NO_PAGE = "Flow is open in a tab of its own, with no page beside it.";
const NO_DESK = "The page beside the chat is not a desk v2 page, so it has no acts to list or run.";

// `claim()` resolves true for the first tab that asks; `reply(answer)` posts `{screen}` or `{error}`.
export async function answerPageCall(
	message,
	{ page, inPanel, claim, reply, deskWait = DESK_WAIT, lateDelay = inPanel ? LATE_DELAY : STANDALONE_DELAY }
) {
	const desk = inPanel ? await waitForDesk(page, deskWait) : null;
	if (!desk) await delay(lateDelay);
	// an act must run once, however many tabs hear the call
	if (message.op === "run_act" && !(await claim())) return;
	if (!desk) return reply({ error: missingDesk(page, inPanel) });
	try {
		reply({ screen: await callDesk(desk, message.op, message.args ?? {}) });
	} catch (error) {
		reply({ error: `The page beside the chat failed: ${error?.message ?? error}` });
	}
}

// what the page shows, for `read_screen`; nothing on a page with no window.desk
export async function readDeskState(page, wait = STATE_WAIT) {
	const desk = usable(page.desk);
	if (!desk) return undefined;
	try {
		return await Promise.race([desk.state(), delay(wait).then(() => undefined)]);
	} catch {
		return undefined;
	}
}

function missingDesk(page, inPanel) {
	if (!inPanel) return NO_PAGE;
	if (page.desk) {
		return `The page's window.desk is version ${page.desk.version}; this chat drives version ${DESK_VERSION}.`;
	}
	return NO_DESK;
}

async function callDesk(desk, op, args) {
	if (op === "list_acts") return listed(await desk.acts.list());
	if (op === "run_act" && args.call != null) return desk.acts.wait(args.call, { timeout: ACT_WAIT });
	if (op === "run_act") return waitForPerson(desk, await desk.acts.run(args.name, args.args ?? undefined));
	throw new Error(`unknown call ${op}`);
}

// A confirm is the person's to answer. The call waits for them here, so the agent's turn goes on
// with the outcome; after ACT_WAIT it is `waiting_for_user` again, and the agent may wait again.
async function waitForPerson(desk, result) {
	const call = result?.error?.code === "waiting_for_user" ? result.error.call : null;
	if (typeof call !== "number") return result;
	return desk.acts.wait(call, { timeout: ACT_WAIT });
}

// screen_result takes an object
const listed = (acts) => (Array.isArray(acts) ? { acts } : acts);

async function waitForDesk(page, wait) {
	const end = Date.now() + wait;
	while (!page.desk && Date.now() < end) await delay(100);
	return usable(page.desk);
}

const usable = (desk) => (desk?.version === DESK_VERSION ? desk : null);

const delay = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
