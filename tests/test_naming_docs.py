# test_naming_docs.py - the GUI naming pages are the markdown files.

from dampf.naming_docs import CHEAT_SHEET, FULL, load_naming_doc, naming_doc_path


def test_how_to_name_is_the_markdown_file():
    sheet_path = naming_doc_path(CHEAT_SHEET)
    full_path = naming_doc_path(FULL)
    assert load_naming_doc(CHEAT_SHEET) == sheet_path.read_text(encoding="utf-8")
    assert load_naming_doc(FULL) == full_path.read_text(encoding="utf-8")


def test_naming_pages_keep_the_three_rules():
    sheet = load_naming_doc(CHEAT_SHEET)
    full = load_naming_doc(FULL)
    for page in (sheet, full):
        assert "column" not in page.lower()
        assert "Separates" in page or "separates" in page
        assert "Glues" in page or "glues" in page
        assert "Defines" in page or "defines" in page
    assert "run=01" in sheet and "Number" in sheet
    assert "4,5kV" in full and "5 kV" in full

