# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

from __future__ import unicode_literals
import frappe
import json
from frappe import _
import copy


def install():
    update_genders_and_salutations()
    make_administrative_area_fixtures()


@frappe.whitelist()
def update_genders_and_salutations():
    default_genders = [_("Male"), _("Female"), _("Other")]
    default_salutations = [_("Mr"), _("Ms"), _('Mx'), _("Dr"), _("Mrs"), _("Madam"), _("Miss"), _("Master"), _("Prof")]
    records = [{'doctype': 'Gender', 'gender': d} for d in default_genders]
    records += [{'doctype': 'Salutation', 'salutation': d} for d in default_salutations]
    for record in records:
        doc = frappe.new_doc(record.get("doctype"))
        doc.update(record)

        try:
            doc.insert(ignore_permissions=True)
        except frappe.DuplicateEntryError as e:
            # pass DuplicateEntryError and continue
            if e.args and e.args[0] == doc.doctype and e.args[1] == doc.name:
                # make sure DuplicateEntryError is for the exact same doc and not a related doc
                pass
            else:
                raise


def make_administrative_area_fixtures():

    administrative_areas = get_administrative_areas()
    frappe.utils.background_jobs.enqueue(
        make_administrative_areas,
        queue="long",
        timeout=36000,
        administrative_areas=administrative_areas,
        enqueue_after_commit=True,
    )


def get_administrative_areas():
    with open("../apps/frappe/frappe/desk/page/setup_wizard/administrative_areas.json") as f:
        return json.loads(f.read())


def make_administrative_areas(administrative_areas):
    """
    ASSUMPTIONS: 1. Administrative_areas file does not have complete duplicates
                 2. There are only 5 levels i.e.country, state, county, city and pincode (hardcoded names)
                 3. In administrative_areas.json child occures after parent

    """
    #enter country administrative area as root node with no parent
    country = frappe.db.get_value("System Settings", "System Settings", "Country")

    if country in administrative_areas.keys():
        country_record = {
            "doctype": "Administrative Area",
            "title": country,
            "administrative_area_type": "country",
            "is_group": 1,
            "lft": 0,
            "rgt": 2*len(administrative_areas[country]) + 1
        }
        make_fixture_record(country_record)
        for record in administrative_areas[country]:
            record.update({
                "parent_unique_name": "".join(record['parent']),
                "self_unique_name": "".join(record['parent']) + "" + record['title']
            })

        """
        Calculate lft, rgt and use db_insert() to speed up
        """
        administrative_states = [area for area in administrative_areas[country] if area['administrative_area_type'] == "state"]
        lft = 1
        for state in administrative_states:
            all_children = [area for area in administrative_areas[country] if area['parent_unique_name'].startswith(state['self_unique_name'])]
            all_county_children = [area for area in administrative_areas[country] if area['parent_unique_name'] == state['self_unique_name']]
            rgt = lft + 2*len(all_children) + 1
            state.update({"lft": lft, "rgt": rgt})
            if (rgt - lft) == 1:
                lft = lft + 2
            else:
                lft = lft + 1
                for county in all_county_children:
                    all_children = [area for area in administrative_areas[country] if area['parent_unique_name'].startswith(county['self_unique_name'])]
                    all_city_children = [area for area in administrative_areas[country] if area['parent_unique_name'] == county['self_unique_name']]
                    rgt = lft + 2*len(all_children) + 1
                    county.update({"lft": lft, "rgt": rgt})
                    if (rgt - lft) == 1:
                        lft = lft + 2
                    else:
                        lft = lft + 1
                        for city in all_city_children:
                            all_children = [area for area in administrative_areas[country] if city['self_unique_name'] in area['parent_unique_name']]
                            all_pincode_children = [area for area in administrative_areas[country] if area['parent_unique_name'] == city['self_unique_name']]
                            rgt = lft + 2*len(all_children) + 1
                            city.update({"lft": lft, "rgt": rgt})
                            if (rgt - lft) == 1:
                                lft = lft + 2
                            else:
                                lft = lft + 1
                                for pincode in all_pincode_children:
                                    pincode.update({"lft": lft, "rgt": lft + 1})
                                    lft = lft + 2
                                lft = lft + 1
                        lft = lft + 1
                lft = lft + 1

        """
        add other administrative areas for the country selected in setup if data available in aa.jaon file
        """

        """
        uncomment in below block to use get_parent_name_alternative() function
        marginally faster but complex
        """
        #administrative_area_types = ['pincode', 'city', 'county', 'state', 'country']
        administrative_areas_copy = copy.deepcopy(administrative_areas)  # copy by value
        for record in administrative_areas[country]:
            #parent_administrative_area_type = administrative_area_types[administrative_area_types.index(record["administrative_area_type"]) + 1]
            #parents = list([country])
            #parents.extend(record["parent"])
            record.update({
                "doctype": "Administrative Area",
                "parent_administrative_area": get_parent_name(country, record, administrative_areas[country], administrative_areas_copy[country]),
                #"parent_administrative_area": get_parent_name_alternative(parents, parent_administrative_area_type),
                "is_group": 1
            })
            del record['parent']
            del record['parent_unique_name']
            del record['self_unique_name']
            make_fixture_record(record)


def get_parent_name(country, record, administrative_areas, administrative_areas_copy):
    if record['parent_unique_name'] == "":
        return country.title()
    else:
        parent_details = [area for area in administrative_areas_copy if area['self_unique_name'] == record['parent_unique_name']]
        if len(parent_details) == 0:
            frappe.throw("wrong parent hierarchy")
        elif len(parent_details) > 1:
            frappe.throw("duplicate entry")
        else:
            parent_name = [admin_area for admin_area in administrative_areas if parent_details[0]['lft'] == admin_area['lft'] and parent_details[0]['rgt'] == admin_area['rgt'] and parent_details[0]['title'] == admin_area['title']]
            return parent_name[0]['name']


def get_parent_name_alternative(parents, parent_administrative_area_type):
    """
    If hierachy has just 1 level (ie.just below country return country name) ( to insert state )

    ##########

    If hierarchy has 2 levels ie. country and state ( to insert county ):

    -Get all name and parent administrative areas of type state with title as given in hierarchyself.
    -These are candiddates for being the correct parent
    -From these candidate state whose parent = country name is correct parent

    ##########

    If hierarchy has more than 2 levels (to insert city, pincode and others)
    -Get all name and parent administrative areas of necessary type with title as given in hierarchyself.
    -These are possible parent candiddates
    -Canadidates whose parent name contains grandparent of doc to be inserted are possible possible_hierarchies
    -If there are more than 1 possible hierarchies than the correct hierachy will be the one  which
        -Either parent name of possible parent contains great grandparent name of doc to be inserted
        -Or parent name of possible parent should be exact match with grandparent name of doc to be inserted

    The above logic will work because the autoname function adds parent name to title in case of duplicate
    """
    if len(parents) == 1:
        return parents[-1]

    elif len(parents) == 2:
        possible_parents = frappe.db.sql("""select t1.name, t1.parent_administrative_area from `tabAdministrative Area` t1 where t1.title='{0}' and t1.administrative_area_type='{1}'""".format(parents[-1], parent_administrative_area_type))
        correct_parent_count = 0
        for parent in possible_parents:
            if parents[-2].title() in parent[1].title():
                correct_parent = parent[0]
                correct_parent_count = correct_parent_count + 1
        if correct_parent_count == 0:
            frappe.throw("wrong parent name")
        else:
            return correct_parent

    else:
        possible_parents = frappe.db.sql("""select t1.name, t1.parent_administrative_area from `tabAdministrative Area` t1 where t1.title='{0}' and t1.administrative_area_type='{1}'""".format(parents[-1], parent_administrative_area_type))
        possible_hierarchies = []
        for parent in possible_parents:
            if parents[-2].title() in parent[1].title():
                possible_hierarchies.append(parent[0])
        if len(possible_hierarchies) == 0:
            frappe.throw("wrong parent name")
        elif len(possible_hierarchies) == 1:
            return possible_hierarchies[-1]
        else:
            contains_grandparent = False
            for hierarchy in possible_hierarchies:
                if parents[-3].title() in hierarchy.title():
                    contains_grandparent = True
                    return hierarchy
            if contains_grandparent is False:
                exact_match = False
                correct_parent = ""
                for hierarchy in possible_hierarchies:
                    if hierarchy.title() == parent[-2].title():
                        exact_match = True
                        correct_parent = hierarchy
                if exact_match:
                    return correct_parent
                else:
                    frappe.throw("wrong parent hierarchy")


def make_fixture_record(record):
    from frappe.modules import scrub
    doc = frappe.new_doc(record.get("doctype"))
    doc.update(record)
    # ignore mandatory for root
    parent_link_field = ("parent_" + scrub(doc.doctype))
    if doc.meta.get_field(parent_link_field) and not doc.get(parent_link_field):
        doc.flags.ignore_mandatory = True

    try:
        doc.db_insert()
        record.update({"name": doc.name})
        frappe.db.commit()
    except frappe.DuplicateEntryError as e:
        # pass DuplicateEntryError and continue
        if e.args and e.args[0] == doc.doctype and e.args[1] == doc.name:
            # make sure DuplicateEntryError is for the exact same doc and not a related doc
            pass
        else:
            raise
    except frappe.ValidationError as e:
        pass
