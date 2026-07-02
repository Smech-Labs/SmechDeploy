fn main() {
    println!("cargo:rustc-link-search=native=/usr/lib/x86_64-linux-gnu");
    println!("cargo:rustc-link-arg=-l:libnewt.so.0.52");
}
