# Use Microsoft's Playwright image as the base
FROM mcr.microsoft.com/playwright:v1.41.1-jammy

# Set the working directory in the container to /app
WORKDIR /app

# Copy the current directory contents into the container at /app
COPY ./scripts /app/scripts
COPY ./requirements.txt /app/requirements.txt
COPY ./ca.crt /usr/local/share/ca-certificates/ca.crt

# Install Python, pip, and other dependencies
RUN apt-get update && \
    apt-get install -y python3 python3-pip && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Install any needed packages specified in requirements.txt
RUN python3 -m pip install --no-cache-dir -r /app/requirements.txt

# Install CA certificates
RUN update-ca-certificates

# Make port 80 available to the world outside this container
EXPOSE 80

# Set environment variables for certificate paths
ENV REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt
ENV NODE_EXTRA_CA_CERTS=/etc/ssl/certs/ca-certificates.crt
ENV PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1

# Run init.py when the container launches
CMD ["python3", "/app/scripts/init.py"]
