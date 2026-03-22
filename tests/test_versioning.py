# tests/test_versioning.py
import pytest


def test_find_existing_version_returns_match():
    from src.versioning import find_existing_version

    existing_docs = [
        {"document_id": "doc-001", "company": "AXA 安盛", "product_name": "智尊守慧", "document_type": "產品小冊子", "is_latest": True},
        {"document_id": "doc-002", "company": "CTF Life", "product_name": "MyWealth", "document_type": "產品小冊子", "is_latest": True},
    ]

    new_meta = {"company": "AXA 安盛", "product_name": "智尊守慧", "document_type": "產品小冊子"}
    match = find_existing_version(new_meta, existing_docs)
    assert match is not None
    assert match["document_id"] == "doc-001"


def test_find_existing_version_returns_none_when_no_match():
    from src.versioning import find_existing_version

    existing_docs = [
        {"document_id": "doc-001", "company": "AXA 安盛", "product_name": "智尊守慧", "document_type": "產品小冊子", "is_latest": True},
    ]

    new_meta = {"company": "AXA 安盛", "product_name": "智尊守慧", "document_type": "培訓資料"}
    match = find_existing_version(new_meta, existing_docs)
    assert match is None


def test_find_existing_version_only_matches_latest():
    from src.versioning import find_existing_version

    existing_docs = [
        {"document_id": "doc-001", "company": "AXA 安盛", "product_name": "智尊守慧", "document_type": "產品小冊子", "is_latest": False},
    ]

    new_meta = {"company": "AXA 安盛", "product_name": "智尊守慧", "document_type": "產品小冊子"}
    match = find_existing_version(new_meta, existing_docs)
    assert match is None
