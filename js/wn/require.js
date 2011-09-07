// require js file
wn.require = function(items) {
	if(typeof items === "string") {
		items = [items];
	}
	var l = items.length;

	for(var i=0; i< l; i++) {
		var src = items[i];
		if(!(src in wn.assets.executed_)) {
			// check if available in localstorage
			wn.assets.execute(src)
		}
	}
}