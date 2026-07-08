use pyo3::prelude::*;

fn quote_identifier(value: &str, quote_char: Option<&str>) -> String {
    match quote_char {
        Some("") | None => value.to_string(),
        Some(quote) => {
            let escaped = value.replace(quote, &(quote.to_owned() + quote));
            format!("{quote}{escaped}{quote}")
        }
    }
}

fn render_select_sql(
    table: &str,
    fields: &[String],
    quote_char: Option<&str>,
    where_sql: Option<&str>,
    orderbys: &[String],
    limit: Option<u64>,
) -> String {
    let select_sql = if fields == ["*"] {
        "*".to_string()
    } else {
        fields
            .iter()
            .map(|field| quote_identifier(field, quote_char))
            .collect::<Vec<_>>()
            .join(",")
    };

    let mut sql = format!(
        "SELECT {select_sql} FROM {}",
        quote_identifier(table, quote_char)
    );
    if let Some(where_sql) = where_sql {
        sql.push_str(" WHERE ");
        sql.push_str(where_sql);
    }
    if !orderbys.is_empty() {
        sql.push_str(" ORDER BY ");
        sql.push_str(&orderbys.join(","));
    }
    if let Some(limit) = limit {
        sql.push_str(&format!(" LIMIT {limit}"));
    }
    sql
}

fn render_select_star_sql(table: &str, quote_char: Option<&str>, limit: Option<u64>) -> String {
    render_select_sql(table, &["*".to_string()], quote_char, None, &[], limit)
}

fn render_insert_sql(
    table: &str,
    columns: &[String],
    rows: &[Vec<String>],
    quote_char: Option<&str>,
) -> String {
    let columns_sql = columns
        .iter()
        .map(|column| quote_identifier(column, quote_char))
        .collect::<Vec<_>>()
        .join(",");
    let values_sql = rows
        .iter()
        .map(|row| format!("({})", row.join(",")))
        .collect::<Vec<_>>()
        .join(",");

    format!(
        "INSERT INTO {} ({columns_sql}) VALUES {values_sql}",
        quote_identifier(table, quote_char)
    )
}

fn render_update_sql(
    table: &str,
    assignments: &[String],
    quote_char: Option<&str>,
    where_sql: Option<&str>,
) -> String {
    let mut sql = format!(
        "UPDATE {} SET {}",
        quote_identifier(table, quote_char),
        assignments.join(",")
    );
    if let Some(where_sql) = where_sql {
        sql.push_str(" WHERE ");
        sql.push_str(where_sql);
    }
    sql
}

fn render_delete_sql(table: &str, quote_char: Option<&str>, where_sql: Option<&str>) -> String {
    let mut sql = format!("DELETE FROM {}", quote_identifier(table, quote_char));
    if let Some(where_sql) = where_sql {
        sql.push_str(" WHERE ");
        sql.push_str(where_sql);
    }
    sql
}

#[pyfunction]
fn version() -> &'static str {
    env!("CARGO_PKG_VERSION")
}

#[pyfunction]
fn capability_summary() -> Vec<&'static str> {
    vec![
        "package-scaffold",
        "pyo3-extension",
        "frappe-first",
        "dialects:mariadb,postgres,sqlite",
        "render-select",
        "render-select-star",
        "render-select-query",
        "render-insert",
        "render-update",
        "render-delete",
    ]
}

#[pyfunction]
#[pyo3(signature = (table, fields, quote_char=None, limit=None))]
fn render_select(
    table: &str,
    fields: Vec<String>,
    quote_char: Option<&str>,
    limit: Option<u64>,
) -> String {
    render_select_sql(table, &fields, quote_char, None, &[], limit)
}

#[pyfunction]
#[pyo3(signature = (table, fields, quote_char=None, where_sql=None, orderbys=None, limit=None))]
fn render_select_query(
    table: &str,
    fields: Vec<String>,
    quote_char: Option<&str>,
    where_sql: Option<&str>,
    orderbys: Option<Vec<String>>,
    limit: Option<u64>,
) -> String {
    let orderbys = orderbys.unwrap_or_default();
    render_select_sql(table, &fields, quote_char, where_sql, &orderbys, limit)
}

#[pyfunction]
#[pyo3(signature = (table, quote_char=None, limit=None))]
fn render_select_star(table: &str, quote_char: Option<&str>, limit: Option<u64>) -> String {
    render_select_star_sql(table, quote_char, limit)
}

#[pyfunction]
#[pyo3(signature = (table, columns, rows, quote_char=None))]
fn render_insert(
    table: &str,
    columns: Vec<String>,
    rows: Vec<Vec<String>>,
    quote_char: Option<&str>,
) -> String {
    render_insert_sql(table, &columns, &rows, quote_char)
}

#[pyfunction]
#[pyo3(signature = (table, assignments, quote_char=None, where_sql=None))]
fn render_update(
    table: &str,
    assignments: Vec<String>,
    quote_char: Option<&str>,
    where_sql: Option<&str>,
) -> String {
    render_update_sql(table, &assignments, quote_char, where_sql)
}

#[pyfunction]
#[pyo3(signature = (table, quote_char=None, where_sql=None))]
fn render_delete(table: &str, quote_char: Option<&str>, where_sql: Option<&str>) -> String {
    render_delete_sql(table, quote_char, where_sql)
}

#[pymodule]
fn _rust(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add_function(wrap_pyfunction!(version, module)?)?;
    module.add_function(wrap_pyfunction!(capability_summary, module)?)?;
    module.add_function(wrap_pyfunction!(render_delete, module)?)?;
    module.add_function(wrap_pyfunction!(render_insert, module)?)?;
    module.add_function(wrap_pyfunction!(render_select, module)?)?;
    module.add_function(wrap_pyfunction!(render_select_query, module)?)?;
    module.add_function(wrap_pyfunction!(render_select_star, module)?)?;
    module.add_function(wrap_pyfunction!(render_update, module)?)?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::{
        render_delete_sql, render_insert_sql, render_select_sql, render_select_star_sql,
        render_update_sql,
    };

    #[test]
    fn renders_star_select_with_limit() {
        assert_eq!(
            render_select_sql(
                "tabRole",
                &["*".to_string()],
                Some("`"),
                None,
                &[],
                Some(20)
            ),
            "SELECT * FROM `tabRole` LIMIT 20"
        );
        assert_eq!(
            render_select_star_sql("tabRole", Some("`"), Some(20)),
            "SELECT * FROM `tabRole` LIMIT 20"
        );
    }

    #[test]
    fn renders_quoted_fields() {
        assert_eq!(
            render_select_sql(
                "tabUser",
                &["name".to_string(), "email".to_string()],
                Some("\""),
                None,
                &[],
                None,
            ),
            "SELECT \"name\",\"email\" FROM \"tabUser\""
        );
    }

    #[test]
    fn escapes_quote_characters() {
        assert_eq!(
            render_select_sql(
                "tab`Role",
                &["na`me".to_string()],
                Some("`"),
                None,
                &[],
                None
            ),
            "SELECT `na``me` FROM `tab``Role`"
        );
    }

    #[test]
    fn renders_where_and_order_by() {
        assert_eq!(
            render_select_sql(
                "tabRole",
                &["name".to_string()],
                Some("`"),
                Some("`name`='Guest'"),
                &["`creation` ASC".to_string()],
                Some(1),
            ),
            "SELECT `name` FROM `tabRole` WHERE `name`='Guest' ORDER BY `creation` ASC LIMIT 1"
        );
    }

    #[test]
    fn renders_write_queries() {
        assert_eq!(
            render_insert_sql(
                "tabSingles",
                &[
                    "doctype".to_string(),
                    "field".to_string(),
                    "value".to_string()
                ],
                &[vec![
                    "'User'".to_string(),
                    "'language'".to_string(),
                    "'en'".to_string()
                ]],
                Some("`"),
            ),
            "INSERT INTO `tabSingles` (`doctype`,`field`,`value`) VALUES ('User','language','en')"
        );
        assert_eq!(
            render_update_sql(
                "tabRole",
                &["`disabled`=0".to_string()],
                Some("`"),
                Some("`name`='Guest'"),
            ),
            "UPDATE `tabRole` SET `disabled`=0 WHERE `name`='Guest'"
        );
        assert_eq!(
            render_delete_sql("tabRole", Some("`"), Some("`name`='Guest'")),
            "DELETE FROM `tabRole` WHERE `name`='Guest'"
        );
    }
}
