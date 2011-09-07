// manage history
// load pages via ajax
// setup the history adapter
// if settings no_history is set, no history will be bound
// this can be used to make it work with legacy

$(document).bind('ready', function() {
	if(wn.settings.no_history) return;
	History.Adapter.bind(window,'statechange',function() {
		var state = History.getState();

		// load the state on the browser		
		wn.page.set(state.hash, state.title);
	});
})
