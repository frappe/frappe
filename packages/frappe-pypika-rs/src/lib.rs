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
    if let Some(limit) = limit {
        sql.push_str(&format!(" LIMIT {limit}"));
    }
    sql
}

fn render_select_star_sql(table: &str, quote_char: Option<&str>, limit: Option<u64>) -> String {
    let mut sql = format!("SELECT * FROM {}", quote_identifier(table, quote_char));
    if let Some(limit) = limit {
        sql.push_str(&format!(" LIMIT {limit}"));
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
    render_select_sql(table, &fields, quote_char, limit)
}

#[pyfunction]
#[pyo3(signature = (table, quote_char=None, limit=None))]
fn render_select_star(table: &str, quote_char: Option<&str>, limit: Option<u64>) -> String {
    render_select_star_sql(table, quote_char, limit)
}

#[pymodule]
fn _rust(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add_function(wrap_pyfunction!(version, module)?)?;
    module.add_function(wrap_pyfunction!(capability_summary, module)?)?;
    module.add_function(wrap_pyfunction!(render_select, module)?)?;
    module.add_function(wrap_pyfunction!(render_select_star, module)?)?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::{render_select_sql, render_select_star_sql};

    #[test]
    fn renders_star_select_with_limit() {
        assert_eq!(
            render_select_sql("tabRole", &["*".to_string()], Some("`"), Some(20)),
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
            ),
            "SELECT \"name\",\"email\" FROM \"tabUser\""
        );
    }

    #[test]
    fn escapes_quote_characters() {
        assert_eq!(
            render_select_sql("tab`Role", &["na`me".to_string()], Some("`"), None),
            "SELECT `na``me` FROM `tab``Role`"
        );
    }
}
