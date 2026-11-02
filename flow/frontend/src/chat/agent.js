import { computed, inject } from "vue";

// The agent in force: a session keeps the one it was created with; otherwise the one a
// new chat starts with. The page, which provides the stores, passes them.
export function useAgent(flow = inject("flow"), page = inject("flowPage")) {
	const locked = computed(() => !!flow.state.sessionId);
	const current = computed(() =>
		locked.value
			? flow.state.session?.agent ??
			  flow.state.sessions.find((session) => session.session_id === flow.state.sessionId)
					?.agent
			: page.state.agent
	);
	// a chat still loading, with no listed row to name its agent, shows none yet
	const title = computed(
		() =>
			page.state.boot.agents.find((agent) => agent.name === current.value)?.title ??
			current.value ??
			(locked.value && flow.state.loading ? "" : "Choose an agent")
	);
	return { locked, current, title };
}
