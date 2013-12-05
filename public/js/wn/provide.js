// Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt 

// provide a namespace
if(!window.wn)wn = {}
wn.provide = function(namespace) {
	// docs: create a namespace //
	var nsl = namespace.split('.');
	var parent = window;
	for(var i=0; i<nsl.length; i++) {
		var n = nsl[i];
		if(!parent[n]) {
			parent[n] = {}
		}
		parent = parent[n];
	}
	return parent;
}

wn.provide("locals");
wn.provide("wn.settings");
wn.provide("wn.utils");
wn.provide("wn.ui");
wn.provide("wn.modules");