// The agent's calls to the desk v2 page beside the panel (`list_acts`, `run_act`). The panel shares
// the page's window, so the chat calls `window.desk` directly: no transport of its own. Every
// answer goes back through `screen_result`, as `read_screen`'s does.
const DESK_VERSION = 1;
const DESK_WAIT = 3000; // ms: window.desk appears a moment after the page boots
const ACT_WAIT = 45000; // ms to wait on a confirm; the call itself waits 60 s on the server
// a tab with nothing to drive answers late, so a tab that can drive is heard first
const LATE_DELAY = 1500;

const NO_PAGE = "Flow is open in a tab of its own, with no page beside it.";
const NO_DESK = "The page beside the chat is not a desk v2 page, so it has no acts to list or run.";

// `claim()` resolves true for the first tab that asks; `reply(answer)` posts `{screen}` or `{error}`.
export async function answerPageCall(
	message,
	{ page, inPanel, claim, reply, deskWait = DESK_WAIT, lateDelay = LATE_DELAY }
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
export async function readDeskState(page) {
	const desk = usable(page.desk);
	if (!desk) return undefined;
	try {
		return await desk.state();
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
	if (op === "run_act") return desk.acts.run(args.name, args.args ?? undefined);
	throw new Error(`unknown call ${op}`);
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
