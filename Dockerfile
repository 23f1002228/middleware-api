FROM python:3.11-slim

WORKDIR /app

# Copy requirements file first to cache the layer
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application source code
COPY . .

# Ensure start.sh has execute permissions and unix line endings (handling windows CRLF)
RUN chmod +x start.sh && sed -i 's/\r$//' start.sh

# Expose port
EXPOSE 10000

# Run the startup script
CMD ["./start.sh"]
