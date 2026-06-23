#![allow(dead_code)]
use std::ffi::{c_char, c_int, c_uint, c_void, CString};
use std::ptr;

#[repr(C)]
pub struct NewtComponentStruct {
    _private: [u8; 0],
}
pub type NewtComponent = *mut NewtComponentStruct;

pub const NEWT_FLAG_RETURNEXIT: c_int = 1 << 0;
pub const NEWT_FLAG_SCROLL: c_int = 1 << 2;
pub const NEWT_FLAG_BORDER: c_int = 1 << 5;
pub const NEWT_FLAG_PASSWORD: c_int = 1 << 11;

#[repr(C)]
struct NewtExitStructUnion {
    co: NewtComponent,
}

#[repr(C)]
struct NewtExitStruct {
    reason: c_int,
    u: NewtExitStructUnion,
}

unsafe extern "C" {
    fn newtInit() -> c_int;
    fn newtFinished() -> c_int;
    fn newtCls();
    fn newtCenteredWindow(width: c_uint, height: c_uint, title: *const c_char) -> c_int;
    fn newtPopWindow();
    fn newtRefresh();
    fn newtDrawRootText(col: c_int, row: c_int, text: *const c_char);
    fn newtSuspend();
    fn newtResume() -> c_int;

    fn newtButton(left: c_int, top: c_int, text: *const c_char) -> NewtComponent;
    fn newtLabel(left: c_int, top: c_int, text: *const c_char) -> NewtComponent;
    fn newtListbox(left: c_int, top: c_int, height: c_int, flags: c_int) -> NewtComponent;
    fn newtListboxAppendEntry(co: NewtComponent, text: *const c_char, data: *const c_void) -> c_int;
    fn newtListboxGetCurrent(co: NewtComponent) -> *mut c_void;
    fn newtEntry(
        left: c_int,
        top: c_int,
        initial: *const c_char,
        width: c_int,
        result: *mut *const c_char,
        flags: c_int,
    ) -> NewtComponent;
    fn newtEntryGetValue(co: NewtComponent) -> *mut c_char;

    fn newtForm(vert_bar: NewtComponent, help_tag: *mut c_void, flags: c_int) -> NewtComponent;
    fn newtFormAddComponent(form: NewtComponent, co: NewtComponent);
    fn newtFormRun(co: NewtComponent, es: *mut NewtExitStruct);
    fn newtFormDestroy(co: NewtComponent);
}

pub fn cs(s: &str) -> CString {
    CString::new(s).unwrap_or_else(|_| CString::new("?").unwrap())
}

pub struct Screen;

impl Screen {
    pub fn init() -> Self {
        unsafe {
            newtInit();
            newtCls();
        }
        Screen
    }

    pub fn finish(&self) {
        unsafe {
            newtFinished();
        }
    }

    pub fn suspend(&self) {
        unsafe { newtSuspend() };
    }

    pub fn resume(&self) {
        unsafe { newtResume() };
    }

    pub fn draw_root_text(&self, col: i32, row: i32, text: &str) {
        let c = cs(text);
        unsafe { newtDrawRootText(col, row, c.as_ptr()) };
    }

    pub fn refresh(&self) {
        unsafe { newtRefresh() };
    }
}

/// Button choice window with a label/message and a single OK-style button.
/// Returns once the button is pressed (or only button if more added later).
pub fn message_window(title: &str, text: &str, button: &str) {
    let width = (text.lines().map(|l| l.len()).max().unwrap_or(20) + 6).max(button.len() + 6) as u32;
    let height = (text.lines().count() + 4) as u32;
    let t = cs(title);
    unsafe {
        newtCenteredWindow(width.max(40), height.max(6), t.as_ptr());
    }

    let form = unsafe { newtForm(ptr::null_mut(), ptr::null_mut(), 0) };
    let mut row = 1;
    for line in text.lines() {
        let lbl = unsafe { newtLabel(2, row, cs(line).as_ptr()) };
        unsafe { newtFormAddComponent(form, lbl) };
        row += 1;
    }
    let btn = unsafe { newtButton(2, row + 1, cs(button).as_ptr()) };
    unsafe { newtFormAddComponent(form, btn) };

    let mut es = NewtExitStruct {
        reason: 0,
        u: NewtExitStructUnion { co: ptr::null_mut() },
    };
    unsafe {
        newtFormRun(form, &mut es);
        newtFormDestroy(form);
        newtPopWindow();
    }
}

/// Listbox choice window: title, prompt text, items (label only, value==index),
/// returns the selected index, or None if list empty.
pub fn listbox_window(title: &str, prompt: &str, items: &[&str], button: &str) -> Option<usize> {
    if items.is_empty() {
        return None;
    }
    let height = items.len().min(10) as i32;
    let width = items
        .iter()
        .map(|s| s.len())
        .max()
        .unwrap_or(20)
        .max(prompt.len())
        .max(20) as u32
        + 8;

    let t = cs(title);
    unsafe {
        newtCenteredWindow(width, (height + 6) as u32, t.as_ptr());
    }

    let form = unsafe { newtForm(ptr::null_mut(), ptr::null_mut(), 0) };
    let lbl = unsafe { newtLabel(1, 0, cs(prompt).as_ptr()) };
    unsafe { newtFormAddComponent(form, lbl) };

    let lb = unsafe { newtListbox(1, 2, height, NEWT_FLAG_RETURNEXIT | NEWT_FLAG_BORDER) };
    for (i, item) in items.iter().enumerate() {
        unsafe { newtListboxAppendEntry(lb, cs(item).as_ptr(), i as *const c_void) };
    }
    unsafe { newtFormAddComponent(form, lb) };

    let btn = unsafe { newtButton(1, height + 3, cs(button).as_ptr()) };
    unsafe { newtFormAddComponent(form, btn) };

    let mut es = NewtExitStruct {
        reason: 0,
        u: NewtExitStructUnion { co: ptr::null_mut() },
    };
    unsafe { newtFormRun(form, &mut es) };

    let cur = unsafe { newtListboxGetCurrent(lb) } as usize;

    unsafe {
        newtFormDestroy(form);
        newtPopWindow();
    }
    Some(cur)
}

/// Multi-field entry window: returns Vec<String> values in same order as prompts.
pub fn entry_window(title: &str, header: &str, prompts: &[(&str, bool)], button: &str) -> Vec<String> {
    let width = prompts
        .iter()
        .map(|(p, _)| p.len())
        .max()
        .unwrap_or(10)
        .max(header.len())
        + 30;

    let t = cs(title);
    unsafe {
        newtCenteredWindow(width as u32, (prompts.len() + 5) as u32, t.as_ptr());
    }

    let form = unsafe { newtForm(ptr::null_mut(), ptr::null_mut(), 0) };
    let hdr = unsafe { newtLabel(1, 0, cs(header).as_ptr()) };
    unsafe { newtFormAddComponent(form, hdr) };

    let mut entries: Vec<NewtComponent> = Vec::new();
    let label_col_width = prompts.iter().map(|(p, _)| p.len()).max().unwrap_or(10) as i32 + 2;

    for (i, (prompt, is_password)) in prompts.iter().enumerate() {
        let row = 2 + i as i32;
        let lbl = unsafe { newtLabel(1, row, cs(prompt).as_ptr()) };
        unsafe { newtFormAddComponent(form, lbl) };
        let flags = if *is_password { NEWT_FLAG_PASSWORD } else { 0 };
        let ent = unsafe {
            newtEntry(
                1 + label_col_width,
                row,
                ptr::null(),
                24,
                ptr::null_mut(),
                flags,
            )
        };
        unsafe { newtFormAddComponent(form, ent) };
        entries.push(ent);
    }

    let btn = unsafe { newtButton(1, 2 + prompts.len() as i32 + 1, cs(button).as_ptr()) };
    unsafe { newtFormAddComponent(form, btn) };

    let mut es = NewtExitStruct {
        reason: 0,
        u: NewtExitStructUnion { co: ptr::null_mut() },
    };
    unsafe { newtFormRun(form, &mut es) };

    let mut results = Vec::new();
    for ent in &entries {
        let val = unsafe { newtEntryGetValue(*ent) };
        let s = if val.is_null() {
            String::new()
        } else {
            unsafe { std::ffi::CStr::from_ptr(val) }.to_string_lossy().into_owned()
        };
        results.push(s);
    }

    unsafe {
        newtFormDestroy(form);
        newtPopWindow();
    }
    results
}
