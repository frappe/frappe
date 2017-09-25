frappe.ui.Camera      = class
{
    constructor (options)
    {
        this.dialog   = new frappe.ui.Dialog();

        this.template =
        `
            <div id="frappe-camera">

            </div>
        `

        this.show     = this.show.bind(this);
        this.hide     = this.hide.bind(this);
        this.on       = this.on.bind(this);
        this.attach   = this.attach.bind(this);

        Webcam.set({
            width: 320,
            height: 240,
            flip_horiz: true,
        })
    }

    show ( )
    {
        this.attach((err) => {
            if ( err )
                throw Error('Unable to attach webcamera.');
            
            this.dialog.set_primary_action(__('Click'), () => {
                this.click();
            });
            
            this.dialog.show();
        });
    }

    hide ( )
    {
        this.dialog.hide();
    }

    on (event, callback)
    {
        if ( event == 'attach' ) {
            this.attach(callback);
        }
    }

    click (callback)
    {
        Webcam.snap((data) => {
            console.log(data);
        });
    }

    attach (callback)
    {
        $(this.dialog.body).append(this.template);

        Webcam.attach('#frappe-camera');

        callback();
    }
};