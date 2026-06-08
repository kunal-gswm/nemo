FROM python:3.11-slim

WORKDIR /app

# Install dependencies for Google Chrome and Xvfb
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    xvfb \
    unzip \
    && rm -rf /var/lib/apt/lists/*

# Install Google Chrome Stable
RUN wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add - \
    && echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google.list \
    && apt-get update \
    && apt-get install -y google-chrome-stable \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Run the bot with Xvfb so undetected-chromedriver can run visibly without a real display
CMD ["xvfb-run", "--server-args=-screen 0 1280x720x24", "python", "bot.py"]
