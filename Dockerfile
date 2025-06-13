FROM python:3.9-slim

# Install rclone
RUN apt-get update && apt-get install -y curl unzip && \
    curl -O https://downloads.rclone.org/rclone-current-linux-amd64.zip && \
    unzip rclone-current-linux-amd64.zip && \
    cd rclone-*-linux-amd64 && \
    cp rclone /usr/bin/ && \
    chmod 755 /usr/bin/rclone && \
    cd .. && \
    rm -rf rclone-*-linux-amd64* && \
    apt-get remove -y curl unzip && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Create directory for rclone config
RUN mkdir -p /root/.config/rclone

# Define environment variables (these can be overridden at runtime)
ENV RCLONE_REMOTE=dispo \
    FOLDER_DEMANDES=Partage/Demandes \
    FOLDER_REPONSES=Partage/Réponses \
    TIMEZONE=Europe/Paris

# You need to provide these at runtime or through secrets:
# ENV EXCHANGE_SERVER=your-exchange-server.com
# ENV EXCHANGE_SECRET_KEY=your-secret-key

# Run the application
CMD ["python", "main.py"]
