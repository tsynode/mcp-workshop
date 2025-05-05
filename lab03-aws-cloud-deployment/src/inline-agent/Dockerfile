FROM python:3.11-slim

WORKDIR /app

# Install git and build dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends git build-essential && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Set build arguments and environment variables
ARG COMMIT_ID=unknown
ENV COMMIT_ID=${COMMIT_ID}
# Disable OpenTelemetry to avoid dependency conflicts
ENV INLINEAGENT_DISABLE_TELEMETRY=true

COPY . .

EXPOSE 8501

CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
