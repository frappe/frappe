// Separate file used to setup resource fetcher before loading the app
// else first request always fails with auto
import { frappeRequest, setConfig } from "frappe-ui"
setConfig("resourceFetcher", frappeRequest)
