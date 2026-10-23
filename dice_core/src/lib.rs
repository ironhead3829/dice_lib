use rand::RngExt; 

pub fn roll(n: u32) -> u32 {
    match n {
        0 => 0,
        1 => 1,
        _ => {
            let mut rng = rand::rng();
            rng.random_range(1..=n)
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_dice() {
        assert_eq!(roll(0), 0);
        assert_eq!(roll(1), 1);
        for _ in 0..100 {
            let r = roll(6);
            assert!(r >= 1 && r <= 6);
        }
    }
}
