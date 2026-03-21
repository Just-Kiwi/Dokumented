"""
Tests for DocumentParser - document parsing for PDF, DOCX, and TXT files.
"""
import pytest
import os
from pathlib import Path
from parsers.doc_parser import DocumentParser


class TestDocumentParserText:
    """Tests for TXT file parsing."""

    def test_parse_txt_file(self, sample_txt_path):
        """Test parsing a TXT file."""
        result = DocumentParser.parse(sample_txt_path)
        assert "Invoice #12345" in result
        assert "Acme Corp" in result
        assert "999.99" in result

    def test_parse_txt_file_with_unicode(self, tmp_path):
        """Test parsing TXT file with unicode content."""
        txt_path = tmp_path / "unicode.txt"
        txt_path.write_text("Invoice #\u00e4\u00f6\u00fc from Caf\u00e9", encoding='utf-8')
        
        result = DocumentParser.parse(str(txt_path))
        assert "\u00e4\u00f6\u00fc" in result
        assert "Caf\u00e9" in result

    def test_parse_txt_file_not_found(self):
        """Test parsing non-existent TXT file raises error."""
        with pytest.raises(FileNotFoundError) as exc_info:
            DocumentParser.parse("nonexistent_file.txt")
        assert "File not found" in str(exc_info.value)

    def test_parse_txt_empty_file(self, tmp_path):
        """Test parsing empty TXT file."""
        txt_path = tmp_path / "empty.txt"
        txt_path.write_text("")
        
        result = DocumentParser.parse(str(txt_path))
        assert result == ""

    def test_parse_txt_multiline(self, tmp_path):
        """Test parsing TXT file with multiple lines."""
        content = "Line 1\nLine 2\nLine 3\n"
        txt_path = tmp_path / "multiline.txt"
        txt_path.write_text(content)
        
        result = DocumentParser.parse(str(txt_path))
        assert "Line 1" in result
        assert "Line 2" in result
        assert "Line 3" in result


class TestDocumentParserUnsupported:
    """Tests for unsupported file formats."""

    def test_parse_unsupported_format(self, tmp_path):
        """Test that unsupported formats raise ValueError."""
        xlsx_path = tmp_path / "data.xlsx"
        xlsx_path.write_bytes(b"fake xlsx content")
        
        with pytest.raises(ValueError) as exc_info:
            DocumentParser.parse(str(xlsx_path))
        assert "Unsupported file format" in str(exc_info.value)

    def test_parse_unsupported_format_case_insensitive(self, tmp_path):
        """Test that file format check handles uppercase extensions."""
        test_path = tmp_path / "file.XLSX"
        test_path.write_bytes(b"fake xlsx content")
        
        with pytest.raises(ValueError) as exc_info:
            DocumentParser.parse(str(test_path))
        assert "Unsupported file format" in str(exc_info.value)


class TestDocumentParserFileNotFound:
    """Tests for file not found scenarios."""

    def test_parse_nonexistent_file(self):
        """Test parsing non-existent file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            DocumentParser.parse("/path/to/nonexistent/file.pdf")

    def test_parse_file_with_spaces_in_path(self, tmp_path):
        """Test parsing file with spaces in path."""
        txt_path = tmp_path / "file with spaces.txt"
        txt_path.write_text("Content with spaces in path")
        
        result = DocumentParser.parse(str(txt_path))
        assert "spaces in path" in result


class TestDocumentParserEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_parse_file_case_insensitive_extension(self, tmp_path):
        """Test file extension handling is case-insensitive."""
        txt_path_upper = tmp_path / "file.TXT"
        txt_path_upper.write_text("Uppercase extension")
        
        result = DocumentParser.parse(str(txt_path_upper))
        assert "Uppercase extension" in result

    def test_parse_dot_file(self, tmp_path):
        """Test parsing files starting with dot."""
        txt_path = tmp_path / ".hidden.txt"
        txt_path.write_text("Hidden file content")
        
        result = DocumentParser.parse(str(txt_path))
        assert "Hidden file content" in result

    def test_parse_file_with_special_characters(self, tmp_path):
        """Test parsing file with special characters in name."""
        txt_path = tmp_path / "file@#$%.txt"
        txt_path.write_text("Special characters content")
        
        result = DocumentParser.parse(str(txt_path))
        assert "Special characters content" in result


class TestDocumentParserMethodAvailability:
    """Tests for method existence and availability."""

    def test_document_parser_has_parse_method(self):
        """Test DocumentParser has parse static method."""
        assert hasattr(DocumentParser, 'parse')
        assert callable(DocumentParser.parse)

    def test_document_parser_has_private_parse_methods(self):
        """Test DocumentParser has private parse methods for each format."""
        assert hasattr(DocumentParser, '_parse_pdf')
        assert hasattr(DocumentParser, '_parse_docx')
        assert hasattr(DocumentParser, '_parse_txt')
