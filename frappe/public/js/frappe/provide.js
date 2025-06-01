// Copyright (c) 2015, nts Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

// provide a namespace
if (!window.nts) window.nts = {};

nts.provide = function (namespace) {
	// docs: create a namespace //
	var nsl = namespace.split(".");
	var parent = window;
	for (var i = 0; i < nsl.length; i++) {
		var n = nsl[i];
		if (!parent[n]) {
			parent[n] = {};
		}
		parent = parent[n];
	}
	return parent;
};

nts.provide("locals");
nts.provide("nts.flags");
nts.provide("nts.settings");
nts.provide("nts.utils");
nts.provide("nts.ui.form");
nts.provide("nts.modules");
nts.provide("nts.templates");
nts.provide("nts.test_data");
nts.provide("nts.utils");
nts.provide("nts.model");
nts.provide("nts.user");
nts.provide("nts.session");
nts.provide("nts._messages");
nts.provide("locals.DocType");

// for listviews
nts.provide("nts.listview_settings");
nts.provide("nts.tour");
nts.provide("nts.listview_parent_route");

// constants
window.NEWLINE = "\n";
window.TAB = 9;
window.UP_ARROW = 38;
window.DOWN_ARROW = 40;

// proxy for user globals defined in desk.js

// API globals
window.cur_frm = null;
