FROM python:3.12-slim
WORKDIR /app

# Copy backend package
COPY . admin/backend/

# Install dependencies directly (not the package itself)
RUN pip install --no-cache-dir \
    "fastapi>=0.115.0" \
    "uvicorn[standard]>=0.32.0" \
    "opensearch-py>=3.1.0" \
    "httpx>=0.28.0" \
    "python-dotenv>=1.2.2" \
    "lightrag-hku>=1.4.0" \
    "python-multipart>=0.0.9"

# Create admin package init files for Python imports
RUN touch admin/__init__.py

CMD ["uvicorn", "admin.backend.main:app", "--host", "0.0.0.0", "--port", "8080"]
