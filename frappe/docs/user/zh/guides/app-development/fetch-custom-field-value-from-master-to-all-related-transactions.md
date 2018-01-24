# Fetch a Field Value from a Document into a Transaction

Let's say, there is a custom field "VAT Number" in Supplier, which should be fetched in Purchase Order.

#### Steps:

1. Create a Custom Field **VAT Number** for *Supplier* document with *Field Type* as **Data**.    
    <img class="screenshot" src="/docs/assets/img/add-vat-number-in-supplier.png">

1. Create another Custom Field **VAT Number** for *Purchase Order* document, but in this case with *Field Type* as **Read Only** or check **Read Only** checkbox. Set the **Options** as `supplier.vat_number`.    
    <img class="screenshot" src="/docs/assets/img/add-vat-number-in-purchase-order.png">

1. Go to the user menu and click "Reload".
1. Now, on selection of Supplier in a new Purchase Order, **VAT Number** will be fetched automatically from the selected Supplier.    
    <img class="screenshot" src="/docs/assets/img/vat-number-fetched.png">
