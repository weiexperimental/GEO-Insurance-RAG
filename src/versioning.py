# src/versioning.py
from typing import Any


def find_existing_version(
    new_metadata: dict[str, Any],
    existing_docs: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """Find an existing document that matches company + product_name + document_type.
    Only matches documents where is_latest is True."""
    company = new_metadata.get("company", "")
    product = new_metadata.get("product_name", "")
    doc_type = new_metadata.get("document_type", "")

    if not company or not product or not doc_type:
        return None

    for doc in existing_docs:
        if (
            doc.get("company") == company
            and doc.get("product_name") == product
            and doc.get("document_type") == doc_type
            and doc.get("is_latest") is True
        ):
            return doc

    return None
