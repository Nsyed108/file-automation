# Start with a base image for Python and Node
FROM python:3.10-slim

# Install system dependencies for Chrome & Selenium
RUN apt-get update && apt-get install -y \
    wget \
    unzip \
    curl \
    gnupg \
    nodejs \
    npm \
    chromium \
    chromium-driver \
    && apt-get clean

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV CHROME_BIN=/usr/bin/chromium

# Create and set the working directory
WORKDIR /app

# Copy backend files
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy the entire project (backend + frontend)
COPY . .

# Build React frontend
RUN cd frontend && npm install && npm run build

# Serve React with Flask by pointing static folder to frontend/build
# The Flask app.py should use: static_folder='frontend/build'
# Already assumed in your earlier code

# Expose Flask port
EXPOSE 5000

# Run the Flask app
CMD ["python", "app.py"]
