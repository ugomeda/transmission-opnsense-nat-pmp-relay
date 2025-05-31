FROM python:3-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends natpmpc transmission-cli \
    && rm -rf /var/lib/apt/lists/*

RUN pip3 install \
    pydantic \
    requests \
    loguru \
    pydantic-settings

WORKDIR /app
COPY relay.py /app/relay.py

CMD ["python3", "/app/relay.py"]
