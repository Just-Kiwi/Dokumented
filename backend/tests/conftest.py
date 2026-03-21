"""
Pytest configuration and fixtures for Dokumented tests.
"""
import pytest
import sys
import os
from pathlib import Path
from unittest.mock import Mock, AsyncMock, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from db.database import Base
from db.models import ScriptLibrary, ExtractionResult, RetryLog, StatusEnum


@pytest.fixture(scope="function")
def test_engine():
    """Create a test database engine."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def test_db(test_engine):
    """Create a test database session for each test."""
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def mock_client():
    """Create mock HTTP client for API testing."""
    from unittest.mock import Mock
    client = Mock()
    client.get = Mock()
    client.post = Mock()
    client.put = Mock()
    client.delete = Mock()
    return client


@pytest.fixture
def mock_websocket():
    """Create mock WebSocket for testing."""
    from unittest.mock import Mock
    ws = Mock()
    ws.accept = Mock()
    ws.send_json = AsyncMock()
    ws.receive_text = AsyncMock()
    return ws


@pytest.fixture
def sample_pdf_path(tmp_path):
    """Create a temporary PDF file for testing."""
    pdf_path = tmp_path / "test.pdf"
    return str(pdf_path)


@pytest.fixture
def sample_docx_path(tmp_path):
    """Create a temporary DOCX file for testing."""
    docx_path = tmp_path / "test.docx"
    return str(docx_path)


@pytest.fixture
def sample_txt_path(tmp_path):
    """Create a temporary TXT file for testing."""
    txt_path = tmp_path / "test.txt"
    txt_path.write_text("Invoice #12345\nFrom: Acme Corp\nTotal: $999.99\nDate: 2024-01-15")
    return str(txt_path)


@pytest.fixture
def sample_invoice_text():
    """Sample invoice text for testing extraction."""
    return """
    INVOICE
    
    Invoice Number: INV-2024-001
    Date: January 15, 2024
    Due Date: February 15, 2024
    
    Bill To:
    Client Company Inc.
    123 Business Street
    New York, NY 10001
    
    From:
    Acme Corporation
    456 Industrial Ave
    Los Angeles, CA 90001
    
    Items:
    | Description | Quantity | Unit Price | Total |
    |-------------|----------|------------|-------|
    | Product A   | 10       | $100.00    | $1,000.00 |
    | Product B   | 5        | $50.00     | $250.00 |
    
    Subtotal: $1,250.00
    Tax (10%): $125.00
    Total: $1,375.00
    
    Payment Terms: Net 30
    """


@pytest.fixture
def sample_schema():
    """Sample extraction schema for testing."""
    return [
        {"name": "invoice_number", "description": "The invoice number", "required": True},
        {"name": "invoice_date", "description": "The invoice date", "required": True},
        {"name": "vendor_name", "description": "Name of the vendor", "required": True},
        {"name": "client_name", "description": "Name of the client", "required": True},
        {"name": "total_amount", "description": "Total amount due", "required": True},
        {"name": "due_date", "description": "Payment due date", "required": False},
    ]


@pytest.fixture
def sample_extracted_json():
    """Sample extracted JSON for testing."""
    return {
        "invoice_number": "INV-2024-001",
        "invoice_date": "January 15, 2024",
        "vendor_name": "Acme Corporation",
        "client_name": "Client Company Inc.",
        "total_amount": "$1,375.00",
        "due_date": "February 15, 2024",
    }


@pytest.fixture
def sample_script(test_db):
    """Create a sample script in the test database."""
    script = ScriptLibrary(
        fingerprint="invoice-standard",
        script_body="""import re
result = {
    'invoice_number': re.search(r'Invoice Number:\\s*(\\S+)', raw_text).group(1) if re.search(r'Invoice Number:\\s*(\\S+)', raw_text) else None,
    'vendor_name': re.search(r'From:\\s*\\n(.+)', raw_text, re.MULTILINE).group(1).strip() if re.search(r'From:\\s*\\n(.+)', raw_text, re.MULTILINE) else None,
}
""",
        version=1,
        success_count=5,
        fail_count=1,
    )
    test_db.add(script)
    test_db.commit()
    test_db.refresh(script)
    return script


@pytest.fixture
def sample_extraction_result(test_db, sample_script):
    """Create a sample extraction result."""
    result = ExtractionResult(
        filename="test_invoice.pdf",
        fingerprint="invoice-standard",
        script_version=1,
        raw_text="Sample invoice text",
        extracted_json={"invoice_number": "INV-001"},
        human_overrides={},
        status=StatusEnum.complete,
    )
    test_db.add(result)
    test_db.commit()
    test_db.refresh(result)
    return result
