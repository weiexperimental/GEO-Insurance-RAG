FROM python:3.12-slim
WORKDIR /app

# Copy backend package
COPY . admin/backend/

# Install dependencies from backend's pyproject.toml
RUN pip install --no-cache-dir uv && \
    cd admin/backend && \
    uv pip install --system .

# Create admin package init files for Python imports
RUN touch admin/__init__.py

CMD ["uvicorn", "admin.backend.main:app", "--host", "0.0.0.0", "--port", "8080"]
