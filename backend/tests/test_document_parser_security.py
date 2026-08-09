from zipfile import ZIP_DEFLATED, ZipFile

from app.services.document_parser import DocumentParser


def test_rejects_disguised_office_document(tmp_path):
    path = tmp_path / "fake.docx"
    path.write_text("not a zip archive", encoding="utf-8")

    parsed = DocumentParser()._parse_sync(str(path))

    assert parsed.is_valid is False
    assert "valid Office document" in (parsed.error or "")


def test_rejects_office_archive_with_unsafe_expansion(tmp_path):
    path = tmp_path / "oversized.docx"
    parser = DocumentParser()
    parser.MAX_ARCHIVE_BYTES = 1_024
    with ZipFile(path, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("word/document.xml", b"0" * (parser.MAX_ARCHIVE_BYTES + 1))

    parsed = parser._parse_sync(str(path))

    assert parsed.is_valid is False
    assert "safe limit" in (parsed.error or "")


def test_rejects_pdf_extension_without_pdf_signature(tmp_path):
    path = tmp_path / "fake.pdf"
    path.write_bytes(b"not-a-pdf")

    parsed = DocumentParser()._parse_sync(str(path))

    assert parsed.is_valid is False
    assert "valid PDF" in (parsed.error or "")
