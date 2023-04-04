# Use an official Python runtime as a parent image
FROM python:3.9-slim-buster

# Set the working directory to /app
WORKDIR /app

# Update and install any necessary dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    curl \
    gnupg \
    unzip \
    build-essential \
    libgconf-2-4 \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Download and install Chrome browser for Linux
RUN wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | apt-key add - && \
    echo "deb https://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list && \
    apt-get update && \
    apt-get install -y google-chrome-stable && \
    rm -rf /var/lib/apt/lists/*

# Download and install Chromedriver
RUN wget -q https://chromedriver.storage.googleapis.com/111.0.5563.64/chromedriver_linux64.zip && \
    unzip -o chromedriver_linux64.zip -d /usr/local/bin && \
    rm chromedriver_linux64.zip && \
    chmod +x /usr/local/bin/chromedriver

# Set the environment variable for Chromedriver
ENV PATH="/app:${PATH}"

# Set the container name
ENV HOSTNAME=web_scraper

# Copy the current directory contents into the container at /app
COPY . /app

# Install the required Python packages
RUN pip install --upgrade pip && \
    pip install -r scraper_requirements.txt

# Prompt the user to enter the scraper arguments before running the container
ENTRYPOINT ["python", "scraper.py"]
CMD ["--help"]

# Clean up after the installation
RUN apt-get clean && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# Make the database directory a volume so that data persists between container runs
VOLUME /path/to/local/database
