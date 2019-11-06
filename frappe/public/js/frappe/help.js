$(window).on('hashchange', page_changed);
$(window).on('load', page_changed);


function page_changed(event) {
    // waiting for page to load completely
    frappe.after_ajax(function () {
        // hide Helpentry that may be from another doctype
        $("#toolbar-help .help-entry").remove();

        var route = frappe.get_route();
        addHelpEntryFromModules(route);
    });
}

function addHelpEntryFromModules(route){
    let relevantNotes = [];
    frappe.db.get_list("Note",{
        fields: ['name', 'module', 'doc_type'],
        filters: {"is_help_article": 1}}).then(notes => {
            if (route[0] === "modules"){
                relevantNotes = notes.filter(function(note){
                    return !(note['module'] || note['doc_type']) || note['module'] === route[1];
                });
            } else if (route.length > 1){
                let dt = route[1];
                let doctypeDoc = frappe.get_doc("DocType", dt);
                let module = doctypeDoc.module;
                relevantNotes = notes.filter(function(note){
                    return !(note['module'] || note['doc_type'])
                        || note['module'] === module || note['doc_type'] === dt;
                });
            } else {
                relevantNotes = notes.filter(function(note){
                    return !(note['module'] || note['doc_type']);
                });
            }
            relevantNotes.map(function(note){
                let label = note["name"];
                let newHelpListEntry =
                    $('<li><a href="#Form/Note/' + label + '">' + label + '</a></li>').addClass(" help-entry");
                $("#toolbar-help").append(newHelpListEntry);
            });
        });
}
