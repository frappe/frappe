# Webhooks

Webhooks are "user-defined HTTP callbacks". You can create webhook which triggers on Doc Event of the selected DocType. When the `doc_events` occurs, the source site makes an HTTP request to the URI configured for the webhook. Users can configure them to cause events on one site to invoke behaviour on another.

#### Configure Webhook

To add Webhook go to

> Integrations > External Documents > Webhook

Webhook

<img class="screenshot" src="/docs/assets/img/webhook.png">

1. Select the DocType for which hook needs to be triggered e.g. Note
2. Select the DocEvent for which hook needs to be triggered e.g. on_trash
3. Enter a valid request URL. On occurence of DocEvent, POST request with doc's json as data is made to the URL.
4. Optionally you can add headers to the request to be made. Useful for sending api key if required.
5. Optionally you can select fields and set its `key` to be sent as data json

e.g. Webhook

- **DocType** : `Quotation`
- **Doc Event** : `on_update`
- **Request URL** : `https://httpbin.org/post`
- **Webhook Data** :
  1. **Fieldname** : `name` and **Key** : `id`
  2. **Fieldname** : `items` and **Key** : `lineItems`

Note: if no headers or data is present, request will be made without any header or body  

Example response of request sent by frappe server on `Quotation` - `on_update` to https://httpbin.org/post:

```
{
  "args": {},
  "data": "{\"lineItems\": [{\"stock_qty\": 1.0, \"base_price_list_rate\": 1.0, \"image\": \"\", \"creation\": \"2017-09-14 13:41:58.373023\", \"base_amount\": 1.0, \"qty\": 1.0, \"margin_rate_or_amount\": 0.0, \"rate\": 1.0, \"owner\": \"Administrator\", \"stock_uom\": \"Unit\", \"base_net_amount\": 1.0, \"page_break\": 0, \"modified_by\": \"Administrator\", \"base_net_rate\": 1.0, \"discount_percentage\": 0.0, \"item_name\": \"I1\", \"amount\": 1.0, \"actual_qty\": 0.0, \"net_rate\": 1.0, \"conversion_factor\": 1.0, \"warehouse\": \"Finished Goods - R\", \"docstatus\": 0, \"prevdoc_docname\": null, \"uom\": \"Unit\", \"description\": \"I1\", \"parent\": \"QTN-00001\", \"brand\": null, \"gst_hsn_code\": null, \"base_rate\": 1.0, \"item_code\": \"I1\", \"projected_qty\": 0.0, \"margin_type\": \"\", \"doctype\": \"Quotation Item\", \"rate_with_margin\": 0.0, \"pricing_rule\": null, \"price_list_rate\": 1.0, \"name\": \"QUOD/00001\", \"idx\": 1, \"item_tax_rate\": \"{}\", \"item_group\": \"Products\", \"modified\": \"2017-09-14 17:09:51.239271\", \"parenttype\": \"Quotation\", \"customer_item_code\": null, \"net_amount\": 1.0, \"prevdoc_doctype\": null, \"parentfield\": \"items\"}], \"id\": \"QTN-00001\"}",
  "files": {},
  "form": {},
  "headers": {
    "Accept": "*/*",
    "Accept-Encoding": "gzip, deflate",
    "Connection": "close",
    "Content-Length": "1075",
    "Host": "httpbin.org",
    "User-Agent": "python-requests/2.18.1"
  },
  "json": {
    "id": "QTN-00001",
    "lineItems": [
      {
        "actual_qty": 0.0,
        "amount": 1.0,
        "base_amount": 1.0,
        "base_net_amount": 1.0,
        "base_net_rate": 1.0,
        "base_price_list_rate": 1.0,
        "base_rate": 1.0,
        "brand": null,
        "conversion_factor": 1.0,
        "creation": "2017-09-14 13:41:58.373023",
        "customer_item_code": null,
        "description": "I1",
        "discount_percentage": 0.0,
        "docstatus": 0,
        "doctype": "Quotation Item",
        "gst_hsn_code": null,
        "idx": 1,
        "image": "",
        "item_code": "I1",
        "item_group": "Products",
        "item_name": "I1",
        "item_tax_rate": "{}",
        "margin_rate_or_amount": 0.0,
        "margin_type": "",
        "modified": "2017-09-14 17:09:51.239271",
        "modified_by": "Administrator",
        "name": "QUOD/00001",
        "net_amount": 1.0,
        "net_rate": 1.0,
        "owner": "Administrator",
        "page_break": 0,
        "parent": "QTN-00001",
        "parentfield": "items",
        "parenttype": "Quotation",
        "prevdoc_docname": null,
        "prevdoc_doctype": null,
        "price_list_rate": 1.0,
        "pricing_rule": null,
        "projected_qty": 0.0,
        "qty": 1.0,
        "rate": 1.0,
        "rate_with_margin": 0.0,
        "stock_qty": 1.0,
        "stock_uom": "Unit",
        "uom": "Unit",
        "warehouse": "Finished Goods - R"
      }
    ]
  },
  "url": "https://httpbin.org/post"
}
```