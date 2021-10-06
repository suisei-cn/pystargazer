FROM python:3.10.0-bullseye as builder

RUN pip install --upgrade pip

RUN mkdir /install

COPY LICENSE ./

COPY README.md setup.py ./

COPY pystargazer ./pystargazer

RUN pip install --user ".[files,mongo,telemetry]"

FROM python:3.10.0-slim-bullseye

ARG TELEMETRY_RELEASE

MAINTAINER LightQuantum

WORKDIR /app

RUN mkdir /plugins

COPY --from=builder /root/.local /root/.local

ENV PYTHONUNBUFFERED=1

ENV PATH=/root/.local:$PATH

ENV PLUGIN_DIR=/plugins

ENV TELEMETRY_RELEASE=${TELEMETRY_RELEASE}

CMD ["python", "-m", "pystargazer"]
