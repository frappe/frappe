import { FORMS } from "./pages/pages.js";

// One page; the route names the open conversation, or the record shown in its place (a record,
// or "new" for a blank one), so links and reloads keep it. The island runs them on a memory
// history; /flow mirrors it into the address bar.
const kinds = FORMS.map((page) => page.key).join("|");
export const routes = [
	{ path: "/", name: "new", component: { render: () => null } },
	{ path: "/s/:session", name: "session", component: { render: () => null } },
	{ path: `/:kind(${kinds})/:record`, name: "records", component: { render: () => null } },
	{ path: "/:rest(.*)", redirect: "/" },
];
