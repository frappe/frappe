nts.provide("nts.model");
nts.provide("nts.utils");

/**
 * Opens the Website Meta Tag form if it exists for {route}
 * or creates a new doc and opens the form
 */
nts.utils.set_meta_tag = function (route) {
	nts.db.exists("Website Route Meta", route).then((exists) => {
		if (exists) {
			nts.set_route("Form", "Website Route Meta", route);
		} else {
			// new doc
			const doc = nts.model.get_new_doc("Website Route Meta");
			doc.__newname = route;
			nts.set_route("Form", doc.doctype, doc.name);
		}
	});
};
