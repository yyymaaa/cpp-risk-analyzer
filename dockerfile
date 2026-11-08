FROM python:3.11-slim

# git is required: the pipeline mines the target repository's history
RUN apt-get update && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/* \
    && git config --system --add safe.directory '*'

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN pip install --no-cache-dir --no-deps -e .

# Usage (mount the target repo under its real folder name, and persist models/data):
#   docker build -t cpp-risk-analyzer .
#   docker run --rm -v /path/to/rocksdb:/repos/rocksdb \
#     -v "$PWD/models:/app/models" -v "$PWD/data:/app/data" \
#     cpp-risk-analyzer build /repos/rocksdb
ENTRYPOINT ["risk"]
CMD ["--help"]
