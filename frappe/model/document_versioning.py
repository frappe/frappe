from __future__ import unicode_literals
import frappe
import datetime
import json


def dump_doc(doc, method=None):
    """
    Dump a doc's json blob into temporary unsorted history table before saving.

    This method can be called from a document hook, or elsewhere. The *method*
    param is optional for this reason, as doc hooks pass it by default.

    :param doc (frappe.model.document.Document)
    :param method (string) (optional)

    """

    if module_is_versionable(doc):
        if hasattr(doc, "__islocal"):
            doc_dict = "{}"
        else:
            doc_dict = frappe.get_doc(doc.doctype, doc.name).as_json()
        storage_doc = frappe.get_doc({
            "doctype": "Doc History Temp",
            "changed_name": doc.name,
            "old_json_blob": doc_dict
        })
        return storage_doc
    return None


def make_json_maybe(blob):
    if blob:
        blob = json.loads(blob)
    return blob


def sort_temp_entries():
    doc_history_list = frappe.get_list(
        "Doc History Temp",
        limit_page_length=None
    )
    for name in doc_history_list:
        doc = frappe.get_doc("Doc History Temp", name['name'])
        old_dict = make_json_maybe(doc.old_json_blob)
        new_dict = make_json_maybe(doc.new_json_blob)
        log_field_changes(new_dict, old_dict)
        doc.delete()


# TODO do we want to delete the history trail?
def clean_history():
    doctype_list = frappe.get_list("DocType", limit_page_length=None)
    for doctype in doctype_list:
        if "Field History" in doctype['name']:
            changed_doctype = doctype['name'].replace(" Field History", "")
            changed_doc_names = frappe.db.sql("""
                SELECT `changed_doc_name` FROM `tab{0}`
                GROUP BY `changed_doc_name`
                """.format(doctype['name']))
            for name in changed_doc_names:
                try:
                    frappe.get_doc(changed_doctype, name[0])
                except:
                    delete_history(changed_doctype, name[0])


def delete_history_event(doc, method):
    """ Called from on-trash document hook. """
    delete_history(doc.doctype, doc.name)


def delete_history(doctype, docname):
    try:
        frappe.db.sql("""
            DELETE FROM `tab{0} Field History`
            WHERE `changed_doc_name` = "{1}"
            """.format(doctype, docname))
    except Exception, e:
        if e.args[0] == 1146:
            pass
        else:
            raise e


# TODO add field-level selection in customize form?
def module_is_versionable(doc):
    """
    Check if a given module is selected to be versioned.

    :param doc (frappe.model.document)

    """
    if (doc.doctype == "Doc History Temp"):
        return False
    if ("Field History" in doc.doctype):
        return False

    module = doc.meta.module
    settings = frappe.db.get_value(
            "Document Versioning Settings",
            "Document Versioning Settings",
            "stored_modules"
        )
    # have to handle installation edge case this way.
    if settings:
        settings = json.loads(settings)
    else:
        settings = {}
    return settings.get(module, False)


def log_field_changes(new_dict, old_dict):
    """
    Compares fields in the new and old document. If different, creates a
    versioning entry.

    :param new_dict (dictionary or None)
    :param old_dict (dictionary or None)

    """

    ignored_fields = ["modified", "creation", "__onload"]
    refs = get_doc_references(new_dict, old_dict)

    if (new_dict is None and old_dict is None):
        raise Exception("No dictionaries passed into log_field_changes.")
    elif (new_dict is None):
        iterable = old_dict
        new_dict = {}
    elif (old_dict is None):
        iterable = new_dict
        old_dict = {}
    else:
        iterable = new_dict

    for fieldname, value in iterable.iteritems():
        if fieldname not in ignored_fields:
            old_value = old_dict.get(fieldname, None)
            new_value = new_dict.get(fieldname, None)
            if old_value != new_value:
                doc = prep_doc(refs, new_value, old_value, fieldname)
                make_doc(doc)


def get_doc_references(new_dict, old_dict):
    """Get references like doctype, docname, etc. """
    if (new_dict is not None):
        refs = {
            "doctype": get_analytics_doctype_name(new_dict['doctype']),
            "changed_doctype": new_dict['doctype'],
            "changed_doc_name": new_dict['name'],
            "modified_by_user": new_dict["modified_by"],
            "date": new_dict["modified"],
        }
    else:
        refs = {
            "doctype": get_analytics_doctype_name(old_dict['doctype']),
            "changed_doctype": old_dict['doctype'],
            "changed_doc_name": old_dict['name'],
            "modified_by_user": old_dict["modified_by"],
            "date": old_dict["modified"],
        }
    return refs


def make_doc(doc):
    """
    Make an entry in the * Field History table for the corresponding doc.

    If the entry is a list or dict, we have to compare the lists and go back to
    log_field_changes recursively.

    :param new_value (*)
    :param old_value (*)
    :param fieldname (string, fieldname being logged)

    """
    if type(doc['new_value']) is not list:
        make_doctype_maybe(doc['doctype'])
        frappe.get_doc(doc).insert()
    else:
        compared_lists = compare_lists(doc['old_value'], doc['new_value'])
        if (compared_lists is not None):
            for entry in compared_lists:
                log_field_changes(entry['new_entry'], entry['old_entry'])


def compare_lists(old_list, new_list):
    """
    Compares two lists to determine which entries are shared.

    :param old_list (list)
    :param new_list (list)

    Returns None if lists are empty, otherwise a list of:
        {
            "new_entry": corresponding entry (or None),
            "old_entry": corresponding entry (or None)
        }

    Steps:
    0. If both lists are empty, return None.
    1. If either list is empty, return mapping with corresponding null values.
       This optimization helps us skip the mapping for newly created docs.
    2. Make hash table of each list with key: entry mapping.
    3. Iterate through old hash, adding to comparison list if values differ.
       Delete k/v pair from new hash if a match is found.
    4. If entries remain in the new hash, the corresponding old value is None.
       We can directly enter them into the comparison list.
    5. Done.

    """

    if (old_list == [] and new_list == []):
        return None
    elif ((old_list is None) or (old_list == [])):
        return [{
            "new_entry": entry,
            "old_entry": None
        } for entry in new_list]
    elif ((new_list is None) or (new_list == [])):
        return [{
            "new_entry": None,
            "old_entry": entry
        } for entry in old_list]

    compared_entries = []
    old_hash = make_hash_for_list(old_list)
    new_hash = make_hash_for_list(new_list)

    for key, old_entry in old_hash.iteritems():
        new_entry = new_hash.get(key, None)
        if (old_entry != new_entry):
            compared_entries.append({
                "new_entry": new_entry,
                "old_entry": old_entry
            })
        # only delete from new_hash if key exists
        if (new_entry is not None):
            del new_hash[key]

    if (new_hash != {}):
        for key, new_entry in new_hash.iteritems():
            compared_entries.append({
                "new_entry": new_entry,
                "old_entry": None
            })

    return compared_entries


def make_hash_for_list(a_list):
    """
    Util to make hash for a list of objects.

    :param a_list (list)

    """

    hash_map = {}
    for entry in a_list:
        hash_map[entry["name"]] = entry
    return hash_map


def prep_doc(refs, new_value, old_value, fieldname):
    """
    Serializes a document to prepare for creating a row in the history table.

    :param refs (dictionary)
    :param new_value (*)
    :param old_value (*)
    :param fieldname (string)

    """

    return {
        "doctype": refs['doctype'],
        "changed_doctype": refs['changed_doctype'],
        "changed_doc_name": refs['changed_doc_name'],
        "fieldname": fieldname,
        "old_value": old_value,
        "new_value": new_value,
        "modified_by_user": refs["modified_by_user"],
        "date": refs["date"],
        }


def get_analytics_doctype_name(doctype):
    return (doctype + " Field History")


def make_doctype_maybe(doctype_name):
    """ Makes doctype for Analytics app, if necessary. """
    try:
        dt = frappe.get_list(
            "DocType",
            filters={"name": doctype_name},
            ignore_permissions=True
            )[0]
    except:
        dt = frappe.get_doc(get_change_doctype_json(doctype_name))
        dt.insert(ignore_permissions=True)


def date_hook(dictionary):
    """ Converts non-serializable types into serializable values. """
    for key, value in dictionary.iteritems():
        if str(type(value)) == "<type 'datetime.datetime'>":
            dictionary[key] = datetime.datetime.strftime(
                value, "%m-%d-%Y %H:%M:%S")
        elif str(type(value)) == "<type 'datetime.date'>":
            dictionary[key] = datetime.datetime.strftime(value, "%m-%d-%Y")
        elif str(type(value)) == "<type 'list'>":
            dictionary[key] = [date_hook(entry) for entry in value]
        elif type(value) == "<type 'dict'>":
            dictionary[key] = date_hook(value)
    return dictionary


def get_change_doctype_json(doctype):
    return {
         "allow_copy": 0,
         "allow_import": 0,
         "allow_rename": 0,
         "creation": "2016-04-17 16:18:44.523847",
         "custom": 1,
         "docstatus": 0,
         "doctype": "DocType",
         "document_type": "Document",
         "fields": [
          {
           "allow_on_submit": 0,
           "bold": 0,
           "collapsible": 0,
           "fieldname": "changed_doc_name",
           "fieldtype": "Data",
           "hidden": 0,
           "ignore_user_permissions": 0,
           "ignore_xss_filter": 0,
           "in_filter": 0,
           "in_list_view": 0,
           "label": "Document Name",
           "length": 0,
           "no_copy": 0,
           "permlevel": 0,
           "precision": "",
           "print_hide": 0,
           "print_hide_if_no_value": 0,
           "read_only": 1,
           "report_hide": 0,
           "reqd": 0,
           "search_index": 0,
           "set_only_once": 0,
           "unique": 0
          },
          {
           "allow_on_submit": 0,
           "bold": 0,
           "collapsible": 0,
           "fieldname": "date",
           "fieldtype": "Datetime",
           "hidden": 0,
           "ignore_user_permissions": 0,
           "ignore_xss_filter": 0,
           "in_filter": 0,
           "in_list_view": 0,
           "label": "Date",
           "length": 0,
           "no_copy": 0,
           "permlevel": 0,
           "precision": "",
           "print_hide": 0,
           "print_hide_if_no_value": 0,
           "read_only": 1,
           "report_hide": 0,
           "reqd": 0,
           "search_index": 0,
           "set_only_once": 0,
           "unique": 0
          },
          {
           "allow_on_submit": 0,
           "bold": 0,
           "collapsible": 0,
           "fieldname": "modified_by_user",
           "fieldtype": "Data",
           "hidden": 0,
           "ignore_user_permissions": 0,
           "ignore_xss_filter": 0,
           "in_filter": 0,
           "in_list_view": 0,
           "label": "Modified By User",
           "length": 0,
           "no_copy": 0,
           "permlevel": 0,
           "precision": "",
           "print_hide": 0,
           "print_hide_if_no_value": 0,
           "read_only": 1,
           "report_hide": 0,
           "reqd": 0,
           "search_index": 0,
           "set_only_once": 0,
           "unique": 0
          },
          {
           "allow_on_submit": 0,
           "bold": 0,
           "collapsible": 0,
           "fieldname": "fieldname",
           "fieldtype": "Data",
           "hidden": 0,
           "ignore_user_permissions": 0,
           "ignore_xss_filter": 0,
           "in_filter": 0,
           "in_list_view": 0,
           "label": "Fieldname",
           "length": 0,
           "no_copy": 0,
           "permlevel": 0,
           "precision": "",
           "print_hide": 0,
           "print_hide_if_no_value": 0,
           "read_only": 1,
           "report_hide": 0,
           "reqd": 0,
           "search_index": 0,
           "set_only_once": 0,
           "unique": 0
          },
          {
           "allow_on_submit": 0,
           "bold": 0,
           "collapsible": 0,
           "fieldname": "old_value",
           "fieldtype": "Code",
           "hidden": 0,
           "ignore_user_permissions": 0,
           "ignore_xss_filter": 0,
           "in_filter": 0,
           "in_list_view": 0,
           "label": "Old Value",
           "length": 0,
           "no_copy": 0,
           "permlevel": 0,
           "precision": "",
           "print_hide": 0,
           "print_hide_if_no_value": 0,
           "read_only": 1,
           "report_hide": 0,
           "reqd": 0,
           "search_index": 0,
           "set_only_once": 0,
           "unique": 0
          },
          {
           "allow_on_submit": 0,
           "bold": 0,
           "collapsible": 0,
           "fieldname": "new_value",
           "fieldtype": "Code",
           "hidden": 0,
           "ignore_user_permissions": 0,
           "ignore_xss_filter": 0,
           "in_filter": 0,
           "in_list_view": 0,
           "label": "New Value",
           "length": 0,
           "no_copy": 0,
           "permlevel": 0,
           "precision": "",
           "print_hide": 0,
           "print_hide_if_no_value": 0,
           "read_only": 1,
           "report_hide": 0,
           "reqd": 0,
           "search_index": 0,
           "set_only_once": 0,
           "unique": 0
          }
         ],
         "hide_heading": 0,
         "hide_toolbar": 0,
         "idx": 0,
         "in_create": 0,
         "in_dialog": 0,
         "is_submittable": 0,
         "issingle": 0,
         "istable": 0,
         "max_attachments": 0,
         "modified": "2016-04-19 19:33:53.699191",
         "modified_by": "Administrator",
         "module": "Core",
         "name": doctype,
         "name_case": "",
         "owner": "Administrator",
         "permissions": [
          {
           "amend": 0,
           "apply_user_permissions": 0,
           "cancel": 0,
           "create": 1,
           "delete": 1,
           "email": 1,
           "export": 1,
           "if_owner": 0,
           "import": 0,
           "permlevel": 0,
           "print": 1,
           "read": 1,
           "report": 1,
           "role": "Administrator",
           "set_user_permissions": 0,
           "share": 1,
           "submit": 0,
           "write": 1
          },
          {
           "amend": 0,
           "apply_user_permissions": 0,
           "cancel": 0,
           "create": 1,
           "delete": 0,
           "email": 1,
           "export": 1,
           "if_owner": 0,
           "import": 0,
           "permlevel": 0,
           "print": 1,
           "read": 1,
           "report": 1,
           "role": "All",
           "set_user_permissions": 0,
           "share": 1,
           "submit": 0,
           "write": 0
           }
         ],
         "read_only": 0,
         "read_only_onload": 0,
         "sort_field": "modified",
         "sort_order": "DESC"
        }
