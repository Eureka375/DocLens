# DocLens V0.1 Implementation Plan

**Goal:** Compare two local TXT or DOCX files in a Windows desktop window.

**Architecture:** Framework-independent parser and diff engine, with a PySide6 controller and a QML window. Worker threads run bounded local comparisons; GUI objects stay on the GUI thread.

**Tech stack:** Python 3.13, PySide6 Essentials, Qt Quick, python-docx, pytest.

**Spec:** Approved DocLens technical review (T02–T05) and the T01 findings.

1. Create an independent source-layout project and Git repository. Verify editable installation in a fresh project environment.
2. Write parser cases for UTF-8/BOM, explicit GB18030, line ranges, DOCX tables and hyperlinks, invalid files, revisions and size limits. Implement `read_document(path, encoding, check_cancelled)` returning an immutable snapshot of ordered text blocks with source coordinates.
3. Test insert/delete/replace, paragraph splitting, repeated text, empty and identical files, numeric edits, bounded fallbacks and cancellation. Implement `compare(left, right, check_cancelled)` returning grouped changes and half-open code point spans, including zero-length navigation anchors on the opposite side.
4. Add a Windows controller/Qt Quick test that loads real paths via the same slots as the file dialogs, waits for comparison, and verifies text, status, highlights, navigation, retry and reset. Implement the UI and its UTF-16 adapter. Inspect a rendered frame.
5. Run the full suite and exercise the normal entry point. Document reproducible setup and test commands, accepted boundaries and the remaining performance/deployment checks.

Scope is the offline comparison milestone. Keep search and AI for the next milestone. Put the project under `outputs/DocLens` so it is accessible from the delivery and isolated from FolioMind and T01.
