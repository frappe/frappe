
export function get_workflow_elements(workflow, workflow_data) {
	let elements = [];
	let states = {};
	let actions = {};
	let transitions = {};

	let x = 150;
	let y = 100;

	workflow_data.forEach(data => {
		if (data.type == 'state') {
			states[data.id] = data
		}
		else if (data.type == 'action') {
			actions[data.id] = data
		}
		else if (data.type == 'transition') {
			transitions[`edge-${data.source}-${data.target}`] = data
		}
	})

	function state_obj(id, data) {

		let state = states[id];

		if (state) {
			state.data = data;
		} else {
			state = {
				id: id.toString(),
				type: "state",
				position: { x, y },
				data,
			};
		}

		return states[id] = state;
	}

	function action_obj(id, data, position) {
		let action = actions[id];

		if (action) {
			data.from_id = action.data.from_id;
			data.to_id = action.data.to_id,
			action.data = data;
		} else {
			action = {
				id,
				type: "action",
				position,
				data,
			};
		}


		return actions[id] = action;
	}

	function transition_obj(id, source, target) {

		let transition = transitions[id];

		if (!transition) {
			transition = {
				id,
				type: "transition",
				source: source.toString(),
				target: target.toString(),
				sourceHandle: "right",
				targetHandle: "left",
				updatable: true,
				animated: true,
			};
		}

		return transitions[id] = transition;

	}

	let state_id = Math.max(...(workflow.states.map(state => state.workflow_builder_id))) || 0;

	workflow.states.forEach((state, i) => {
		x += 400;
		let doc_status_map = {
			0: "Draft",
			1: "Submitted",
			2: "Cancelled",
		};

		const id = state.workflow_builder_id || ++state_id;
		elements.push(
			state_obj(id, {
				...state,
				doc_status: doc_status_map[state.doc_status],
			})
		);
	});

	let action_id = Math.max(...(workflow.transitions.map(transition => transition.workflow_builder_id?.replace('action-', '')))) || 0;

	workflow.transitions.forEach((transition, i) => {
		const id = transition.workflow_builder_id || ('action-' + (++action_id));
		let action = actions[id];
		let source, target;

		if (action && action.data.from_id && action.data.to_id) {
			source = states[action.data.from_id];
			target = states[action.data.to_id];
		} else {
			source = Object.values(states).filter(state => state.data.state == transition.state)[0];
			target =  Object.values(states).filter(state => state.data.state == transition.next_state)[0];
		}

		let position =  {x: source.position.x + 250, y:  y + 20 };
		let data = {
			...transition,
			from_id: source.id,
			to_id: target.id,
			from: transition.state,
			to: transition.next_state,
		};

		elements.push(action_obj(id, data, position));
		elements.push(transition_obj('edge-' + source.id + "-" + id, source.id, id));
		elements.push(transition_obj('edge-' + id + "-" + target.id, id, target.id));
	});

	return elements;
}

export function validate_transitions(state, next_state) {
	let message;
	if (state.doc_status == "Cancelled") {
		message = __("Cannot change state of Cancelled Document <b>({0} State)</b>", [
			state.state,
		]);
	}

	if (state.doc_status == "Submitted" && next_state.doc_status == "Draft") {
		message = __(
			"Submitted document cannot be converted back to draft while transitioning from <b>{0} State</b> to <b>{1} State</b>",
			[state.state, next_state.state]
		);
	}

	if (state.doc_status == "Draft" && next_state.doc_status == "Cancelled") {
		message = __(
			"Cannot cancel before submitting while transitioning from <b>{0} State</b> to <b>{1} State</b>",
			[state.state, next_state.state]
		);
	}
	return message;
}
