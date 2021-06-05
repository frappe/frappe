frappe.ui.form.FormTour = class FormTour {
    constructor({ frm }) {
        this.frm = frm;
        this.driver_steps = [];

        this.init_driver();
    }

    init_driver() {
        this.driver = new frappe.Driver({
			className: 'frappe-driver',
			allowClose: false,
			padding: 10,
			overlayClickNext: true,
			keyboardControl: true,
			nextBtnText: 'Next',
			prevBtnText: 'Previous',
			opacity: 0.25
		});

        frappe.router.on('change', () => this.driver.reset());
        this.frm.layout.sections.forEach(section => section.collapse(false));
    }

    async init({ tour_name, on_finish }) {
        if (tour_name) {
            this.tour = await frappe.db.get_doc('Form Tour', tour_name);
        } else {
            this.tour = { steps: frappe.tour[this.frm.doctype] }
        }
        
        if (on_finish) this.on_finish = on_finish;

        this.build_steps();
        this.define_steps();
    }

    build_steps() {
        this.tour.steps.forEach((step, idx) => {
            const me = this;
            const on_next = () => {
                const next_condition_satisfied = this.frm.layout.evaluate_depends_on_value(step.next_step_condition || true);

                if (!next_condition_satisfied) {
                   me.driver.preventMove();
                }

                if (!me.driver.hasNextStep()) {
                    me.on_finish && me.on_finish();
                }
            }

            const driver_step = this.get_step(step, on_next);
			this.driver_steps.push(driver_step);
        });
    }

    get_step(step_info, on_next) {
        const field = this.frm.get_field(step_info.fieldname);
        // if field is a child table field, `field` will be undefined
        const element = field ? field.wrapper : `.frappe-control[data-fieldname='${step_info.fieldname}']`;
        const title = step_info.title || field.df.label;
        const description = step_info.description;
        const position = step_info.position || 'bottom';
        return {
            element,
            popover: { title, description, position },
            onNext: on_next
        };
    }

    define_steps(steps = []) {
        if (steps.length == 0) {
            steps = this.driver_steps;
        }
        this.driver.defineSteps(steps);
    }

    start() {
        if (this.driver_steps.length == 0) {
            return;
        }
		this.driver.start();
    }
};