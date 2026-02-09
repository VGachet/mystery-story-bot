FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY src/ src/

# Create data & output directories
RUN mkdir -p data output

# Default: run the main pipeline
CMD ["python", "-m", "src.main"]
