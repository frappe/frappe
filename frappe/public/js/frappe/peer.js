frappe.Peer 	  = class 
{
	constructor ( )
	{
		this.peer = new Peer()
		this.peer.on('open', (ID) => {
			console.log(`A new peer connection has occured with ID: ${ID}`)
		})
	}
}

frappe.Peer.boot = ( ) =>
{
	const client = new frappe.Peer()
}