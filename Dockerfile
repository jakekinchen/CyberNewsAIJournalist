# Use an official Python runtime as a parent image
FROM python:3.9-slim-buster

# Set the working directory in the container to /app
WORKDIR /app

# Copy the current directory contents into the container at /app
COPY ./scripts /app/scripts
COPY ./requirements.txt /app/requirements.txt

# Install any needed packages specified in requirements.txt
RUN python3 -m ensurepip --upgrade
RUN pip3 install --no-cache-dir -r /app/requirements.txt
# Install w-get
RUN apt-get update && apt-get install -y wget
# Install openssl
RUN apt-get install -y openssl
# Download the CA certificate
RUN wget -O /usr/local/share/ca-certificates/CA-BrightData.crt https://help.brightdata.com/hc/en-us/article_attachments/6843466967057
# Update the certificates
RUN update-ca-certificates
# Make sure the certificate is downloaded
RUN cat /usr/local/share/ca-certificates/CA-BrightData.crt

# Make port 80 available to the world outside this container
EXPOSE 80

# Run controller.py when the container launches
CMD ["python", "/app/scripts/init.py"]
