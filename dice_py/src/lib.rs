use pyo3::prelude::*;
use dice_core::roll as rust_roll;

#[pyfunction]
fn roll(n: u32) -> PyResult<u32> {
    Ok(rust_roll(n))
}

#[pymodule]
fn dice_py(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(roll, m)?)?;
    Ok(())
}
