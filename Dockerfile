# Use an official Python runtime as a parent image
FROM python:3.9-slim-buster

# Set the working directory in the container to /app
WORKDIR /app

# Copy the current directory contents into the container at /app
COPY ./scripts /app/scripts
COPY ./requirements.txt /app/requirements.txt

# Install any needed packages specified in requirements.txt
RUN python3 -m ensurepip --upgrade
RUN pip install playwright==1.38
RUN python -m playwright install chromium
RUN pip3 install --no-cache-dir -r /app/requirements.txt

# Make port 80 available to the world outside this container
EXPOSE 80

# Run controller.py when the container launches
CMD ["python", "/app/scripts/init.py"]
