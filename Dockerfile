# Use an official Python runtime as a parent image
# Match the Python version you want to use, e.g., 3.11, 3.12, etc.
FROM python:3.13-slim

# Set environment variables to prevent Python from buffering stdout/stderr
ENV PYTHONUNBUFFERED 1

# Set the working directory in the container
WORKDIR /app

# --- This is the crucial part that fixes the error ---
# As root, update apt and install the build tools
RUN apt-get update && apt-get install -y build-essential python3-dev && rm -rf /var/lib/apt/lists/*

# Copy the requirements file into the container
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of your application code into the container
COPY . .

# --- IMPORTANT: The command to run your app ---
# Render will automatically use the PORT environment variable
# Replace 'myproject.wsgi:application' with the correct path to your app's WSGI object
CMD ["gunicorn", "myproject.wsgi:application", "--bind", "0.0.0.0:10000"]
