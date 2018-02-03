# Translations

<!-- jinja -->
<!-- static -->

This document shows how to translations are managed in ERPNext and how to add
a new language or update translations of an existing language.

### 1. Source

Translatable text exists in 3 main sources:

  1. Javascript Code Files (both framework and application)
  2. Python Code Files
  3. DocTypes (names, labels and select options)

#### Strings in Code Files

Strings in code files are annotated using the `_` (underscore) method

  1. In Python it is the `frappe._` method. Example:

`frappe._("String {0} must be translated".format(txt))`

  2. In Javascript it is the `__` method. Example:

`__("String {0} must be translated", [txt])`

**Note:** If you find translatable strings are not properly annotated using the `_`
method, you can add them in the code and rebuild the translations.

### 2. How Translations Are Picked up During Execution

Whenever a translation is called via the _ method, the entire translation
dictionaries from all apps are built and stored in memcache.

Based on the user preferences or request preferences, the appropriate
translations are loaded at the time of request on the server side. Or if
metadata (DocType) is queried, then the appropriate translations are appended
when the DocType data is requested.

The underscore `_` method will replace the strings based on the available
translations loaded at the time.

### 3. Adding New Translations

1. To find untranslated strings, run `bench get-untranslated [lang] [path]`
1. Add the translated strings in another file in the same order
1. run `bench update-translations [lang] [path of untranslated strings] [path of translated strings]`

### 4. Improving Translations:

For updating translations, please go to the to [the translation portal](https://frappe.io/translator).

If you want to do it directly via code:

To improve an existing translation, just edit the master translation files in
the `translations` of each app

> Please contribute your translations back to ERPNext by sending us a Pull
Request.

### 5. Bootstrapping a New Language

If you want to add a new language it is similar to adding new translations. You need to first export all the translations strings in one file, get them translated via Google Translate Tool or Bing Translate Tool and then import the translations into individual apps.

**Step 1: Export to a file**

	$ bench get-untranslated [lang] [path]

**Step 2: Translate**

Create another file with updated translations (in the same order as the source file). For this you can use the [Google Translator Toolkit](https://translate.google.com/toolkit) or [Bing Translator](http://www.bing.com/translator/).

**Step 3: Import your translations**

	$ bench update-translations [lang] [source path] [translated path]

**Step 4: Update `languages.txt`**

Add your language in `apps/languages.txt` and also `frappe/data/languages.txt` (fore new bench installs)

**Step 5: Commit each app and push**

A new file will be added to the `translations` folder in each app. You need to add that file and push to your repo. Then send us a pull-request.

---

