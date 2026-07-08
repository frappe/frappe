use pyo3::prelude::*;

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
    ]
}

#[pymodule]
fn _rust(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add_function(wrap_pyfunction!(version, module)?)?;
    module.add_function(wrap_pyfunction!(capability_summary, module)?)?;
    Ok(())
}
