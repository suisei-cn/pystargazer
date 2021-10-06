FROM python:3.10.0-slim

ARG TELEMETRY_RELEASE

MAINTAINER LightQuantum

WORKDIR /app

RUN pip install --upgrade pip

COPY LICENSE ./

COPY README.md setup.py ./

COPY pystargazer ./pystargazer

RUN pip install ".[files,mongo,telemetry]"

RUN mkdir /plugins

ENV PYTHONUNBUFFERED=1

ENV PLUGIN_DIR=/plugins

ENV TELEMETRY_RELEASE=${TELEMETRY_RELEASE}

CMD ["python", "-m", "pystargazer"]
