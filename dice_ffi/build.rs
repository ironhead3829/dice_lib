use std::env;
use std::path::PathBuf;

fn main() {
    let crate_dir = env::var("CARGO_MANIFEST_DIR").unwrap();
    let package_name = env::var("CARGO_PKG_NAME").unwrap();
    let out_dir = PathBuf::from(env::var_os("OUT_DIR").unwrap());
    // OUT_DIR is <profile>/build/<package-hash>/out, including cross builds.
    let output_dir = out_dir
        .ancestors()
        .nth(3)
        .expect("OUT_DIR must be inside Cargo's profile directory");
    let output_file = output_dir.join(format!("{}.h", package_name));

    cbindgen::generate(crate_dir)
        .expect("Unable to generate C bindings")
        .write_to_file(output_file);
}
