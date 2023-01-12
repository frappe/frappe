import os
import csv

import frappe

from babel.messages.catalog import Catalog
from babel.messages.pofile import write_po


def csv_to_po(file: str, localedir: str):
    l = os.path.split(file)[-1].split('.')[0]
    m = os.path.join(localedir, l, 'LC_MESSAGES')
    os.makedirs(m, exist_ok=True)
    p = os.path.join(m, 'messages.po')
    c = Catalog()

    with open(file, 'r') as f:
        r = csv.reader(f)

        for row in r:
            if len(row) <= 2:
                continue

            msgid = row[0]
            msgstr = row[1]
            msgctxt = row[2] if len(row ) >= 3 else None

            c.add(msgid, string=msgstr, context=msgctxt)

    with open(p, 'wb') as f:
        write_po(f, c)


def migrate():
    apps = frappe.get_all_apps()
    for app in apps:
        app_path = frappe.get_pymodule_path(app)
        translations_path = os.path.join(app_path, 'translations')

        if not os.path.exists(translations_path):
            continue

        if not os.path.isdir(translations_path):
            continue

        po_locale_dir = os.path.join(app_path, 'locale')
        csv_files = [i for i in os.listdir(translations_path) if i.endswith('sl.csv')] # TODO: remove sl.
        
        for f in csv_files:
            csv_to_po(os.path.join(translations_path, f), po_locale_dir)
