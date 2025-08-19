# Use a stable, well-supported Python version
FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED 1
WORKDIR /app

# Install build tools
RUN apt-get update && apt-get install -y build-essential python3-dev && rm -rf /var/lib/apt/lists/*

# Install Python packages
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

# Run the app
CMD ["python", "run_app.py"]
