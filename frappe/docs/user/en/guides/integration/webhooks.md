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
