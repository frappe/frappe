# This documentation is added for query builder and related files.

## Related Files

- [builder](./builder.py)
- [custom](./custom.py)
- [functions](./functions.py)
- [terms](./terms.py)
- [query](../database/query.py)

### Builder

Database specefic classes are declared which are then selected during init to give either postgres or mariadb dialects.

### Functions and Custom

These file handle any custom function which needs to be either added or handled sperately by the different dialects which are not supported yet by pypika directly.

### Terms

The inherent terms or specefic classes of pypika builder are handled and declared here all the parameterization goes through this module (custom parameterization is also implemeted here).

### Raw Query Generation Examples

Check out some examples [here](https://frappeframework.com/docs/v14/user/en/api/query-builder)

<H2 align="center">Query</H2>

## Goal

```sql
select `name` from `tabUser`
```

## There are 3 major ways to reach this goal

### 1. Direct SQL (Boring / Unsafe / inconsistent)

```python
frappe.db.sql("select `name` from `tabUser`")
```

### 2. SQL through direct Query Builder objects

```python
from frappe.query_builder import Field

frappe.qb.from_("User").select(Field("name"))

```

### 3. Through the database API (Which performs the second method under the hood)

```python
frappe.db.get_values("User", fieldname="name", filters={})
```

This module is used to support the 3rd way of query generation in frappe.
The database module is completely powered by this query module.
This module is also where the query `Engine` resides which is the class responsible for the handling of various filter & field notations.

- Interating with the existing Database API.
  - The old database API was running on raw sql generation in order to bridge the gap between the added new support and raw sql strings this intermediate module was added.

This module supports almost all the features present in db_query which powers `frappe.get_all` and `frappe.get_list`

Supporting all the features with the previous filter notations and the field notations few features were added -:

1. Dict Query

   - To support this

   ```python
       frappe.db.get_values("ToDo", fieldname="name", filters={"description": "Something Random"})
   ```

   and many other possible caveats to the dict representation such as

   ```python
      frappe.db.get_values("User", fieldname="name",
      filters={"name": ("like", "admin%")})

      frappe.db.get_values("ToDo", fieldname="name", filters={"description": ("in", ["somso%", "someome"])})
   ```

2. Misc Query

   - To support this

     ```python
     frappe.db.get_values("ToDo", fieldname="name", filters=["description", "=", "someone"])
     ```

   Along with other possible list filter use cases including implicit joins

3. Criterion Query

   - To support Inherent Query Builder objects

   ```python
   from frappe.query_builder import Field

   frappe.db.get_values("User", fieldname="name", filters=Field("name") == "Administrator")

   ```

   and all the pypika filters and functions.

## Things to be implemented in the `Engine`

### 1. Support for Permissions

As of now query builder has no concept of permissions and moving towards a singular database API this needs to be added in the `Engine`.

### 2. Implementing the missing features which are present in `frappe.get_list` and `frappe.get_all` (do we even need so much magic?)

Moving to a singular Database API (database.py + db_query.py) all the support present in `get_list` and `get_all` needs to be present in the new `Engine` as well however this creates alot of security cracks, so moving the a *new and more restrictive version* of the database API with backward compatibility perhaps would be the right way to go?
