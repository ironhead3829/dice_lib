use std::panic::{catch_unwind, AssertUnwindSafe};

#[unsafe(no_mangle)]
pub extern "C" fn c_roll(n: u32) -> u32 {
    let result = catch_unwind(AssertUnwindSafe(|| {
        dice_core::roll(n)
    }));
    
    match result {
        Ok(val) => val,
        Err(_) => 0, // Return a fallback safe value
    }
}
