import frappe
from datetime import datetime, timedelta
from frappe.utils import (
    date_diff,
    now,
    nowdate,
    flt,
    getdate,
    cint,
)
import calendar


@frappe.whitelist()
def get_employee_info(user=None, checkin_type=None, half_day=None):
    if not user:
        user = frappe.session.user
    FMT = "%H:%M:%S"
    data = []
    flag = 0
    office_out_flag = 0
    date = datetime.strptime(str(nowdate()), "%Y-%m-%d")
    t = datetime.now().time().strftime(FMT)
    time = datetime.strptime(str(t), FMT)
    emp = frappe.db.sql(
        """
				select e.name as employee, e.employee_name, e.department,
    			ifnull((select b.shift_type from `tabAssign Shift` b, `tabShift Details` sd, `tabShift Type` st where sd.parent = b.name and sd.employee = e.employee and b.shift_type = st.name and MONTHNAME('{1}') = b.month and YEAR('{1}') = b.fiscal_year and sd.{2} = 1 and b.docstatus = 1),e.default_shift) as shift_type,
				e.division, e.section, e.designation
				from `tabEmployee` e
				where e.user_id = "{3}"
	""".format(
            time, date, str(date.day), user
        ),
        as_dict=True,
    )
    leave = frappe.db.sql(
        """
		select name from `tabLeave Application` where half_day = 1 and employee = '{0}' and '{1}' between from_date and to_date and docstatus = 1
					""".format(
            emp[0].employee, date
        ),
        as_dict=True,
    )

    att_request = frappe.db.sql(
        """
		select name from `tabAttendance Request` where employee = '{0}'
		and '{1}' between from_date and to_date and half_day = 1
    """.format(
            emp[0].employee, date.date()
        ),
        as_dict=1,
    )
    if (
        leave
        and leave[0].name != None
        and leave[0].name != ""
        and emp[0].shift_type == "General Shift"
    ):
        leave_type = frappe.db.get_value(
            "Leave Application", leave[0].name, "half_day_type"
        )
        if leave_type == "Second Half":
            actual_start_time = datetime.strptime(
                str(frappe.db.get_value("Shift Type", emp[0].shift_type, "start_time")),
                FMT,
            )
            actual_start_time = actual_start_time.time()
            actual_et = datetime.strptime(
                str(
                    frappe.db.get_value(
                        "Shift Type", emp[0].shift_type, "first_half_time"
                    )
                ),
                FMT,
            )
            actual_end_time = actual_et.time()
        elif leave_type == "First Half":
            actual_st = datetime.strptime(
                str(
                    frappe.db.get_value(
                        "Shift Type", emp[0].shift_type, "second_half_time"
                    )
                ),
                FMT,
            )
            actual_start_time = actual_st.time()
            actual_end_time = datetime.strptime(
                str(frappe.db.get_value("Shift Type", emp[0].shift_type, "end_time")),
                FMT,
            )
            actual_end_time = actual_end_time.time()
    elif att_request and att_request[0].name != None and att_request[0].name != "":
        half_day_type = frappe.db.get_value(
            "Attendance Request", att_request[0].name, "half_day_type"
        )
        if half_day_type == "Second Half":
            actual_start_time = datetime.strptime(
                str(frappe.db.get_value("Shift Type", emp[0].shift_type, "start_time")),
                FMT,
            )
            actual_start_time = actual_start_time.time()
            actual_et = datetime.strptime(
                str(
                    frappe.db.get_value(
                        "Shift Type", emp[0].shift_type, "first_half_time"
                    )
                ),
                FMT,
            )
            actual_end_time = actual_et.time()
        elif half_day_type == "First Half":
            actual_st = datetime.strptime(
                str(
                    frappe.db.get_value(
                        "Shift Type", emp[0].shift_type, "second_half_time"
                    )
                ),
                FMT,
            )
            actual_start_time = actual_st.time()
            actual_end_time = datetime.strptime(
                str(frappe.db.get_value("Shift Type", emp[0].shift_type, "end_time")),
                FMT,
            )
            actual_end_time = actual_end_time.time()
    elif int(half_day) == 1:
        actual_start_time = datetime.strptime(
            str(frappe.db.get_value("Shift Type", emp[0].shift_type, "start_time")), FMT
        )
        actual_start_time = actual_start_time.time()
        actual_et = datetime.strptime(
            str(
                frappe.db.get_value("Shift Type", emp[0].shift_type, "first_half_time")
            ),
            FMT,
        )
        actual_end_time = actual_et.time()
    else:
        actual_start_time = datetime.strptime(
            str(frappe.db.get_value("Shift Type", emp[0].shift_type, "start_time")), FMT
        )
        actual_start_time = actual_start_time.time()
        actual_end_time = datetime.strptime(
            str(frappe.db.get_value("Shift Type", emp[0].shift_type, "end_time")), FMT
        )
        actual_end_time = actual_end_time.time()

    ct = checkin_type.split(" ")

    if ct[0] == "Office" and ct[1] == "IN":
        if time.time() > actual_end_time:
            frappe.throw("Invalid Office IN time", title="Cannot Checkin")
        # frappe.throw(str(actual_start_time)+" "+str(actual_end_time))
        tdelta = time - datetime.strptime(str(actual_start_time), FMT)
    elif ct[0] == "Office" and ct[1] == "OUT":
        tdelta = datetime.strptime(str(actual_end_time), FMT) - time
    else:
        tdelta = 0

    if time.time() > actual_start_time:
        flag = 1
        if tdelta != 0:
            time_difference = tdelta.seconds / 60 / 60
        else:
            time_difference = 0
    else:
        time_difference = 0

    if time.time() < actual_end_time:
        office_out_flag = 1
    else:
        time_difference = 0

    data.append(
        {
            "employee": emp[0].employee,
            "employee_name": emp[0].employee_name,
            "shift_type": emp[0].shift_type,
            "time": str(time.time()),
            "time_difference": flt(time_difference, 2),
            "actual_start_time": str(actual_start_time),
            "flag": flag,
            "oo_flag": office_out_flag,
        }
    )

    return data if data else data


@frappe.whitelist()
def make_employee_checkin(
    employee,
    employee_name,
    shift_type,
    time,
    time_difference,
    reason=None,
    checkin_type=None,
):
    if checkin_type != "":
        ct = str(checkin_type).split(" ")
        if ct[0] == "Lunch" and ct[1] == "OUT":
            start_time = frappe.db.get_value("Shift Type", shift_type, "start_time")
            hour = int(frappe.db.get_value("Shift Type", shift_type, "hours_before_lo"))
            hours_added = timedelta(hours=hour)
            future_date_and_time = start_time + hours_added
            if datetime.strptime(str(time), "%H:%M:%S") < datetime.strptime(
                str(future_date_and_time), "%H:%M:%S"
            ):
                frappe.throw("You cannot lunch out before " + str(hour) + " hour(s)")
        doc = frappe.new_doc("Employee Checkin")
        doc.employee = employee
        doc.emplyoee_name = frappe.db.get_value("Employee", employee, "employee_name")
        doc.log_type = ct[1]
        doc.type = ct[0]
        doc.shift = shift_type
        doc.date = datetime.strptime(str(nowdate()), "%Y-%m-%d")
        doc.time_difference = flt(time_difference, 2)
        if reason != None:
            doc.reason = reason
        doc.save(ignore_permissions=True)
    else:
        doc = frappe.new_doc("Employee Checkin")
        doc.employee = employee
        doc.emplyoee_name = frappe.db.get_value("Employee", employee, "employee_name")
        doc.log_type = "IN"
        doc.type = "Office"
        doc.shift = shift_type
        doc.date = datetime.strptime(str(nowdate()), "%Y-%m-%d")
        doc.time_difference = flt(time_difference, 2)
        if reason != None:
            doc.reason = reason
        doc.save(ignore_permissions=True)


@frappe.whitelist()
def get_employee_checkin_info(user=None):
    half_day = 0
    holiday_flag = 0
    half_day_leave = 0
    if not user:
        user = frappe.session.user
    date = datetime.strptime(str(nowdate()), "%Y-%m-%d")
    day = calendar.day_name[date.weekday()]
    # frappe.throw(str(date))
    if user not in ("Administrator", "System Manager"):
        employee = frappe.db.get_value("Employee", {"user_id": user}, "name")
        holiday_list = get_holiday_list_for_employee(employee)

        leave_details = frappe.db.sql(
            """
			select name, half_day from `tabLeave Application` where employee = '{0}'and '{1}' between from_date and to_date and half_day = 1
			and workflow_state = 'Approved'
		""".format(
                employee, date.date()
            )
        )

        if leave_details:
            half_day_leave = 1
        if holiday_list:
            holidays = frappe.db.sql(
                """
					select a.holiday_date from `tabHoliday` a where a.parent = '{0}' and a.holiday_date = '{1}'
            	""".format(
                    holiday_list, date
                ),
                as_dict=1,
            )

            if holidays:
                holiday_flag = 1

            half_working_days = frappe.db.sql(
                """
				select day from `tabHoliday List Days` where parent = '{0}'
        	""".format(
                    holiday_list
                ),
                as_dict=1,
            )

            flag = 0

            for a in half_working_days:
                if day == a.day and flag == 0:
                    half_day = 1
                    flag = 1
            if half_day == 0:
                attendance_request = frappe.db.sql(
                    """
					select name from `tabAttendance Request` where employee = '{0}'
					and '{1}' >= from_date and '{1}' <= to_date and half_day = 1
					and docstatus = 1
                """.format(
                        employee, date
                    )
                )
                if attendance_request:
                    half_day = 1

    data = frappe.db.sql(
        """
				select ec.type,ec.log_type,ec.date as att_date,ec.time as att_time
				from `tabEmployee Checkin` ec
				where ec.date = "{}" and ec.owner = "{}" order by creation desc limit 1
	""".format(
            date, user
        ),
        as_dict=True,
    )
    if data:
        checkin_type = data[0].type + " " + data[0].log_type
    else:
        checkin_type = " "

    return checkin_type, half_day, holiday_flag, half_day_leave


@frappe.whitelist()
def get_display_time():
    d_time = []
    curr_time = frappe.format_value(now(), {"fieldtype": "Time"})
    d_time.append({"d_time": curr_time})
    # frappe.throw(d_time)
    return d_time


@frappe.whitelist()
def get_checkin_info(user):
    data = []
    office_in = lunch_out = lunch_in = office_out = "00:00:00"
    cur_date = datetime.strptime(str(nowdate()), "%Y-%m-%d")

    checkin_data = frappe.db.sql(
        """
			select ec.type,ec.log_type,date_format(ec.date, '%d-%m-%Y') as att_date,time_format(ec.time, "%H:%i %p") as att_time
			from `tabEmployee Checkin` ec
			where ec.date = "{}" and ec.owner = "{}"
		""".format(
            cur_date, user
        ),
        as_dict=True,
    )

    for a in checkin_data:
        if a.type == "Office" and a.log_type == "IN":
            office_in = a.att_time
        elif a.type == "Lunch" and a.log_type == "OUT":
            lunch_out = a.att_time
        elif a.type == "Lunch" and a.log_type == "IN":
            lunch_in = a.att_time
        elif a.type == "Office" and a.log_type == "OUT":
            office_out = a.att_time

    data.append(
        {
            "office_in": office_in,
            "lunch_out": lunch_out,
            "lunch_in": lunch_in,
            "office_out": office_out,
            "date": str(cur_date).split(" ")[0],
        }
    )

    return data


@frappe.whitelist()
def get_checkin_data(user, month):
    # frappe.throw(month)
    default_shift = frappe.db.get_value("Employee", {"user_id": user}, "default_shift")
    in_time = frappe.db.get_value("Shift Type", {"name": default_shift}, "start_time")
    out_time = frappe.db.get_value("Shift Type", {"name": default_shift}, "end_time")
    # frappe.throw(str(otime))
    data = []
    cur_date = datetime.strptime(str(nowdate()), "%Y-%m-%d")
    year = str(cur_date).split("-")[0]
    checkin_list = frappe.db.sql(
        """
				select ec.employee, date_format(ec.date, '%d-%m-%Y') as att_date, date_format(ec.date, '%M') as cmonth,
				date_format(ec.date, '%Y') as cyr
				from `tabEmployee Checkin` ec
				where  ec.owner = "{}"
				and date_format(ec.date, '%M') = "{}"
				and date_format(ec.date, '%Y') = "{}"
	""".format(
            user, month, year
        ),
        as_dict=True,
    )

    for b in checkin_list:
        office_in = lunch_out = lunch_in = office_out = "Not Punch"
        employee = b.employee
        month = b.cmonth
        year = b.cyr
        checkin_data = frappe.db.sql(
            """
				select ec.type,ec.log_type,date_format(ec.date, '%d-%m-%Y') as att_date,time_format(ec.time, "%H:%i %p") as att_time
				from `tabEmployee Checkin` ec
				where  ec.employee = "{}"
				and date_format(ec.date, '%M') = "{}"
				and date_format(ec.date, '%Y') = "{}"
				""".format(
                employee, month, year
            ),
            as_dict=True,
        )
        for a in checkin_data:
            if b.att_date == a.att_date:
                if a.type == "Office" and a.log_type == "IN":
                    office_in = a.att_time
                elif a.type == "Lunch" and a.log_type == "OUT":
                    lunch_out = a.att_time
                elif a.type == "Lunch" and a.log_type == "IN":
                    lunch_in = a.att_time
                elif a.type == "Office" and a.log_type == "OUT":
                    office_out = a.att_time
        data.append(
            {
                "office_in": office_in,
                "lunch_out": lunch_out,
                "lunch_in": lunch_in,
                "office_out": office_out,
                "date": b.att_date,
            }
        )

    new_data = []
    for a in data:
        if a not in new_data:
            new_data.append(a)
    data = new_data
    # sorting the data based on date in descending
    data.sort(key=lambda r: r["date"], reverse=True)

    return data


@frappe.whitelist()
def get_job_description(user):
    data = []
    emp = frappe.db.sql(
        """
            SELECT 
            	name, 
                branch, 
                designation 
            FROM 
            	`tabEmployee` 
            WHERE 
            	user_id = '{}'
        """.format(
            user
        ),
        as_dict=True,
    )
    employee = emp[0].name
    if "Branch Manager" in frappe.get_roles(user):
        jd = frappe.db.sql(
            """
            select attachment from `tabJob Description` where particular = '{0}'
                     """.format(
                emp[0].branch
            ),
            as_dict=True,
        )
    else:
        jd = frappe.db.sql(
            """
            select attachment from `tabJob Description` where particular = '{0}'
                     """.format(
                emp[0].designation
            ),
            as_dict=True,
        )
    # frappe.msgprint(str(jd))
    if jd:
        if jd[0].attachment != None or jd[0].attachment != "":
            data.append({"job_description": jd[0].attachment})
    else:
        data.append({"job_description": "None"})

    return data


@frappe.whitelist()
def get_emp_info(user):
    data = []
    info = frappe.db.sql(
        """
			SELECT 
            	name, 
                grade, 
                designation 
			FROM 
            	`tabEmployee`
			WHERE 
            	user_id = "{}"
		""".format(
            user
        ),
        as_dict=True,
    )
    if info:
        info = info[0]
        data.append(
            {
                "name": info.name,
                "grade": info.grade,
                "designation": info.designation,
            }
        )
    return info


# -----Leaves Details Dashboard----------
@frappe.whitelist()
def get_leave_details(user):
    emp = frappe.db.sql(
        """
            SELECT 
            	name 
            FROM 
            	`tabEmployee` 
            WHERE 
            	user_id = '{}'
        """.format(
            user
        ),
        as_dict=True,
    )
    employee = emp[0].name
    cur_date = datetime.strptime(str(nowdate()), "%Y-%m-%d")
    allocation_records = get_leave_allocation_records(employee, cur_date)
    leave_allocation = {}
    for d in allocation_records:
        allocation = allocation_records.get(d, frappe._dict())
        remaining_leaves = get_leave_balance_on(
            employee,
            d,
            cur_date,
            to_date=allocation.to_date,
            consider_all_leaves_in_the_allocation_period=True,
        )
        end_date = allocation.to_date
        leaves_taken = (
            get_leaves_for_period(employee, d, allocation.from_date, end_date) * -1
        )
        leaves_pending = get_pending_leaves_for_period(
            employee, d, allocation.from_date, end_date
        )

        leave_allocation[d] = {
            "total_leaves": allocation.total_leaves_allocated,
            "leaves_taken": leaves_taken,
            "pending_leaves": leaves_pending,
            "remaining_leaves": remaining_leaves,
        }

    ret = {
        "leave_allocation": leave_allocation,
    }

    return ret


@frappe.whitelist()
def get_pms_records(user):
    emp = frappe.db.sql(
        """
            SELECT 
            	name 
            FROM 
            	`tabEmployee` 
            WHERE 
            	user_id = '{}'
        """.format(
            user
        ),
        as_dict=True,
    )
    employee = emp[0].name
    pms_records = frappe.db.sql(
        """
        	SELECT 
            	fiscal_year, 
                final_score, 
                overall_rating
            FROM 
            	`tabEmployee PMS Rating` 
            WHERE 
				parent = '{0}' 
            ORDER BY 
            	fiscal_year DESC
    	""".format(
            employee
        ),
        as_dict=True,
    )

    return pms_records


@frappe.whitelist()
def get_emp_work_history(user):
    emp = frappe.db.sql(
        """
        	SELECT 
            	name 
            FROM 
            	`tabEmployee`
            WHERE
              	user_id = '{}'
        """.format(
            user
        ),
        as_dict=True,
    )
    employee = emp[0].name
    history = frappe.db.sql(
        """
        	SELECT 
            	reference_doctype, 
                reference_docname, 
                branch, department, 
                division, designation, 
                from_date, 
                to_date, 
                promotion_due_date 
            FROM 
            	`tabEmployee Internal Work History` 
            WHERE
             	parent = '{0}'
        	ORDER BY 
            	reference_doctype 
                DESC
        """.format(
            employee
        ),
        as_dict=True,
    )

    return history


@frappe.whitelist()
def get_training_history(user):
    emp = frappe.db.sql(
        """
        	SELECT 
            	name 
            FROM
            	`tabEmployee` 
            WHERE
             	user_id = '{}'
        """.format(
            user
        ),
        as_dict=True,
    )
    employee = emp[0].name
    history = frappe.db.sql(
        """
        select training_type, training_category, country, course_title, college_training_institute,
        start_date, end_date, duration from `tabEmployee Training History` where parent = '{0}'
        order by start_date desc
                             """.format(
            employee
        ),
        as_dict=True,
    )

    return history


@frappe.whitelist()
def get_disciplinary_records(user):
    emp = frappe.db.sql(
        """
                          select name from `tabEmployee` where user_id = '{}'
                          """.format(
            user
        ),
        as_dict=True,
    )
    employee = emp[0].name
    disciplinary = frappe.db.sql(
        """
        select disciplinary_action_taken, nature, from_date, complaint_frequency, action_taken,
        disciplinary_record from `tabEmployee Disciplinary Summary` where parent = '{0}'
        order by from_date desc
                             """.format(
            employee
        ),
        as_dict=True,
    )

    return disciplinary


def get_leave_allocation_records(employee, date, leave_type=None):
    """returns the total allocated leaves and carry forwarded leaves based on ledger entries"""

    conditions = ("and leave_type='%s'" % leave_type) if leave_type else ""
    allocation_details = frappe.db.sql(
        """
		SELECT
			SUM(CASE WHEN is_carry_forward = 1 THEN leaves ELSE 0 END) as cf_leaves,
			SUM(CASE WHEN is_carry_forward = 0 THEN leaves ELSE 0 END) as new_leaves,
			MIN(from_date) as from_date,
			MAX(to_date) as to_date,
			leave_type
		FROM `tabLeave Ledger Entry`
		WHERE
			from_date <= %(date)s
			AND to_date >= %(date)s
			AND docstatus=1
			AND transaction_type in ("Leave Allocation", "Merge CL To EL")
			AND employee=%(employee)s
			AND is_expired=0
			AND is_lwp=0
			{0}
		GROUP BY employee, leave_type
	""".format(
            conditions
        ),
        dict(date=date, employee=employee),
        as_dict=1,
    )  # nosec

    allocated_leaves = frappe._dict()
    for d in allocation_details:
        allocated_leaves.setdefault(
            d.leave_type,
            frappe._dict(
                {
                    "from_date": d.from_date,
                    "to_date": d.to_date,
                    "total_leaves_allocated": flt(d.cf_leaves) + flt(d.new_leaves),
                    "unused_leaves": d.cf_leaves,
                    "new_leaves_allocated": d.new_leaves,
                    "leave_type": d.leave_type,
                }
            ),
        )
    return allocated_leaves


def get_leave_balance_on(
    employee,
    leave_type,
    date,
    to_date=None,
    consider_all_leaves_in_the_allocation_period=False,
):
    """
    Returns leave balance till date
    :param employee: employee name
    :param leave_type: leave type
    :param date: date to check balance on
    :param to_date: future date to check for allocation expiry
    :param consider_all_leaves_in_the_allocation_period: consider all leaves taken till the allocation end date
    """

    if not to_date:
        to_date = nowdate()

    allocation_records = get_leave_allocation_records(employee, date, leave_type)
    allocation = allocation_records.get(leave_type, frappe._dict())

    end_date = (
        allocation.to_date if consider_all_leaves_in_the_allocation_period else date
    )
    expiry = get_allocation_expiry(employee, leave_type, to_date, date)

    leaves_taken = get_leaves_for_period(
        employee, leave_type, allocation.from_date, end_date
    )

    return get_remaining_leaves(allocation, leaves_taken, date, expiry)


def get_allocation_expiry(employee, leave_type, to_date, from_date):
    """Returns expiry of carry forward allocation in leave ledger entry"""

    expiry = frappe.db.sql(
        """ 
            	select to_date from `tabLeave Ledger Entry` where
				employee = {}
				and leave_type = '{}'
				and is_carry_forward = 1
				and transaction_type = 'Leave Allocation'
				and to_date between '{}' and '{}'
		""".format(
            employee, leave_type, from_date, to_date
        ),
        as_dict=True,
    )
    return expiry[0]["to_date"] if expiry else None


def get_leaves_for_period(
    employee, leave_type, from_date, to_date, do_not_skip_expired_leaves=False
):
    leave_entries = get_leave_entries(employee, leave_type, from_date, to_date)
    leave_days = 0

    for leave_entry in leave_entries:
        inclusive_period = leave_entry.from_date >= getdate(
            from_date
        ) and leave_entry.to_date <= getdate(to_date)

        if inclusive_period and leave_entry.transaction_type == "Leave Encashment":
            leave_days += leave_entry.leaves

        elif (
            inclusive_period
            and leave_entry.transaction_type == "Leave Allocation"
            and leave_entry.is_expired
            and (
                do_not_skip_expired_leaves
                or not skip_expiry_leaves(leave_entry, to_date)
            )
        ):
            leave_days += leave_entry.leaves

        elif leave_entry.transaction_type == "Leave Application":
            if leave_entry.from_date < getdate(from_date):
                leave_entry.from_date = from_date
            if leave_entry.to_date > getdate(to_date):
                leave_entry.to_date = to_date

            half_day = 0
            half_day_date = None
            # fetch half day date for leaves with half days
            if leave_entry.leaves % 1:
                half_day = 1
                half_day_date = frappe.db.get_value(
                    "Leave Application",
                    {"name": leave_entry.transaction_name},
                    ["half_day_date"],
                )

            leave_days += (
                get_number_of_leave_days(
                    employee,
                    leave_type,
                    leave_entry.from_date,
                    leave_entry.to_date,
                    half_day,
                    half_day_date,
                    holiday_list=leave_entry.holiday_list,
                )
                * -1
            )

    return leave_days


def get_leave_entries(employee, leave_type, from_date, to_date):
    """Returns leave entries between from_date and to_date."""
    return frappe.db.sql(
        """
		SELECT
			employee, leave_type, from_date, to_date, leaves, transaction_name, transaction_type, holiday_list,
			is_carry_forward, is_expired
		FROM `tabLeave Ledger Entry`
		WHERE employee=%(employee)s AND leave_type=%(leave_type)s
			AND docstatus=1 
			AND (leaves<0
				OR is_expired=1)
			AND (from_date between %(from_date)s AND %(to_date)s
				OR to_date between %(from_date)s AND %(to_date)s
				OR (from_date < %(from_date)s AND to_date > %(to_date)s))
	""",
        {
            "from_date": from_date,
            "to_date": to_date,
            "employee": employee,
            "leave_type": leave_type,
        },
        as_dict=1,
    )


def get_remaining_leaves(allocation, leaves_taken, date, expiry):
    """Returns minimum leaves remaining after comparing with remaining days for allocation expiry"""

    def _get_remaining_leaves(remaining_leaves, end_date):
        # hidden by kinley : logic of below code is correct which is calculating remaining days in the year from current date and showing how much leaves can be availded by an employee
        # if remaining_leaves > 0:
        # 	remaining_days = date_diff(end_date, date) + 1
        # 	remaining_leaves = min(remaining_days, remaining_leaves)

        return remaining_leaves

    total_leaves = flt(allocation.total_leaves_allocated) + flt(leaves_taken)

    if expiry and allocation.unused_leaves:
        remaining_leaves = flt(allocation.unused_leaves) + flt(leaves_taken)
        remaining_leaves = _get_remaining_leaves(remaining_leaves, expiry)

        total_leaves = flt(allocation.new_leaves_allocated) + flt(remaining_leaves)

    return _get_remaining_leaves(total_leaves, allocation.to_date)


def get_pending_leaves_for_period(employee, leave_type, from_date, to_date):
    """Returns leaves that are pending approval"""
    leaves = frappe.get_all(
        "Leave Application",
        filters={"employee": employee, "leave_type": leave_type, "status": "Open"},
        or_filters={
            "from_date": ["between", (from_date, to_date)],
            "to_date": ["between", (from_date, to_date)],
        },
        fields=["SUM(total_leave_days) as leaves"],
    )[0]
    return leaves["leaves"] if leaves["leaves"] else 0.0


def get_number_of_leave_days(
    employee,
    leave_type,
    from_date,
    to_date,
    half_day=None,
    half_day_date=None,
    holiday_list=None,
):
    number_of_days = 0
    if cint(half_day) == 1:
        if from_date == to_date:
            number_of_days = 0.5
        elif half_day_date and half_day_date <= to_date:
            number_of_days = date_diff(to_date, from_date) + 0.5
        else:
            number_of_days = date_diff(to_date, from_date) + 1

    else:
        number_of_days = date_diff(to_date, from_date) + 1

    if not frappe.db.get_value("Leave Type", leave_type, "include_holiday"):
        number_of_days = flt(number_of_days) - flt(
            get_holidays(employee, from_date, to_date, holiday_list=holiday_list)
        )
    return number_of_days


@frappe.whitelist()
def get_holidays(employee, from_date, to_date, holiday_list=None):
    """get holidays between two dates for the given employee"""
    if not holiday_list:
        holiday_list = get_holiday_list_for_employee(employee)
    holidays = frappe.db.sql(
        """select count(distinct holiday_date) from `tabHoliday` h1, `tabHoliday List` h2
		where h1.parent = h2.name and h1.holiday_date between %s and %s
		and h2.name = %s""",
        (from_date, to_date, holiday_list),
    )[0][0]

    return holidays


# @frappe.whitelist()
# def get_energy_points_heatmap_data(user, date):
# 	return dict(frappe.db.sql("""select unix_timestamp(date(creation)), sum(points)
# 		from `tabEnergy Point Log`
# 		where
# 			date(creation) > subdate('{date}', interval 1 year) and
# 			date(creation) < subdate('{date}', interval -1 year) and
# 			user = '{user}' and
# 			type != 'Review'
# 		group by date(creation)
# 		order by creation asc""".format(user = user, date = date)))

# @frappe.whitelist()
# def get_energy_points_percentage_chart_data(user, field):
# 	result = frappe.db.get_all('Energy Point Log',
# 		filters = {'user': user, 'type': ['!=', 'Review']},
# 		group_by = field,
# 		order_by = field,
# 		fields = [field, 'ABS(sum(points)) as points'],
# 		as_list = True)

# 	return {
# 		"labels": [r[0] for r in result if r[0] != None],
# 		"datasets": [{
# 			"values": [r[1] for r in result]
# 		}]
# 	}


@frappe.whitelist()
def update_profile_info(profile_info):
    profile_info = frappe.parse_json(profile_info)
    keys = ["location", "interest", "user_image", "bio"]

    for key in keys:
        if key not in profile_info:
            profile_info[key] = None

    user = frappe.get_doc("User", frappe.session.user)
    user.update(profile_info)
    user.save()
    return user


# @frappe.whitelist()
# def get_energy_points_list(start, limit, user):
# 	return frappe.db.get_list('Energy Point Log',
# 		filters = {'user': user, 'type': ['!=', 'Review']},
# 		fields = ['name','user', 'points', 'reference_doctype', 'reference_name', 'reason',
# 			'type', 'seen', 'rule', 'owner', 'creation', 'revert_of'],
# 		start = start,
# 		limit = limit,
# 		order_by = 'creation desc')
