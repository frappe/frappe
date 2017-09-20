# Using the Data Migration Tool

> Data Migration Tool was introduced in Frappé Framework version 9.

The Data Migration Tool was built to abstract all the syncing of data between a remote source and a DocType. This is a middleware layer between your Frappé based website and a remote data source.

To understand this tool, let's make a connector to push ERPNext Items to an imaginary service called Atlas.

### Data Migration Plan
A Data Migration Plan encapsulates a set of mappings.

Let's make a new *Data Migration Plan*. Set the plan name as 'Atlas Sync'. We also need to add mappings in the mappings child table.

<img class="screenshot" alt="New Data Migration Plan" src="/docs/assets/img/data-migration/new-data-migration-plan.png">


### Data Migration Mapping
A Data Migration Mapping is a set of rules that specify field-to-field mapping. You can also pre and post process the data if required.

Make a new *Data Migration Mapping*. Call it 'Item to Atlas Item'.

There are a couple of fields which define the Local and Source Data.

1. Remote Objectname - A name that identifies the remote object e.g Atlas Item
1. Remote primary key - This is the name of the primary key for Atlas Item e.g id
1. Local DocType - The DocType which will be used for syncing e.g Item
1. Mapping Type - Push/Pull/Sync (Sync is a combination of Push and Pull)
1. Page Length - This defines the batch size of the sync.

<img class="screenshot" alt="New Data Migration Mapping" src="/docs/assets/img/data-migration/new-data-migration-mapping.png">

Now, let's add the field mappings:

<img class="screenshot" alt="Add fields in Data Migration Mapping" src="/docs/assets/img/data-migration/new-data-migration-mapping-fields.png">

As the name suggests, the Remote fieldname identifies the fields in the Remote Object. Now this can be a column in a table, or property of a JSON object.

The Local Fieldname can take fields from DocType (for e.g `item_name`), literal values in quotes (for e.g `"GadgetTech"`) and eval statements (for e.g `"eval:frappe.db.get_value('Company', 'Gadget Tech', 'default_currency')"`)

Let's go back to our Data Migration Plan and save it.

<img class="screenshot" alt="Save Atlas Sync Plan" src="/docs/assets/img/data-migration/atlas-sync-plan.png">

### Data Migration Connector
Now, to connect to the remote source, we need to create a *Data Migration Connector*.

<img class="screenshot" alt="New Data Migration Connector" src="/docs/assets/img/data-migration/new-connector.png">

We only have two connector types right now, let's add another Connector Type in the Data Migration Connector DocType.

<img class="screenshot" alt="Add Connector Type in Data Migration Connector" src="/docs/assets/img/data-migration/add-connector-type.png">

Now, let's create a new Data Migration Connector.

<img class="screenshot" alt="Atlas Connector" src="/docs/assets/img/data-migration/atlas-connector.png">

As you can see we chose the Connector Type as Atlas. We also added the hostname, username and password for our Atlas instance so that we can authenticate.

Now, we need to write the code for our connector so that we can actually push data.

Create a new file called `atlas_connection.py` in `frappe/data_migration/doctype/data_migration_connector/connectors/` directory. Other connectors also live here.

We just have to implement the `insert`, `update` and `delete` methods for our atlas connector. We also need to write the code to connect to our Atlas instance in the `__init__` method. Just see `frappe_connection.py` for reference.

<img class="screenshot" alt="Atlas Connection file" src="/docs/assets/img/data-migration/atlas-connection-py.png">

After creating the Atlas Connector, we also need to import it into `data_migration_connector.py`

<img class="screenshot" alt="Edit Connector file" src="/docs/assets/img/data-migration/edit-connector-py.png">

### Data Migration Run
Now that we have our connector, the last thing to do is to create a new *Data Migration Run*.

A Data Migration Run takes a Data Migration Plan and Data Migration Connector and execute the plan according to our configuration. It takes care of queueing, batching, delta updates and more.

<img class="screenshot" alt="Data Migration Run" src="/docs/assets/img/data-migration/data-migration-run.png">

Just click Run. It will now push our Items to the remote Atlas instance and you can see the progress which updates in realtime.

After a run is executed successfully, you cannot run it again. You will have to create another run and execute it.

Data Migration Run will try to be as efficient as possible, so the next time you execute it, it will only push those items which were changed or failed in the last run.


> Note: Data Migration Tool is still in beta. If you find any issues please report them [here](https://github.com/frappe/erpnext/issues)

<!-- markdown -->