FROM python:3.8.2-slim

MAINTAINER LightQuantum

WORKDIR /app

RUN pip install --upgrade pip

COPY LICENSE ./

COPY README.md setup.py ./

COPY pystargazer ./pystargazer

RUN pip install ".[files,mongo]"

RUN mkdir /plugins

ENV PYTHONUNBUFFERED=1

ENV PLUGIN_DIR=/plugins

CMD ["python", "-m", "pystargazer"]
