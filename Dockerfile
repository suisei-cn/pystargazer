FROM python:3.8.2-slim

MAINTAINER LightQuantum

WORKDIR /app

COPY LICENSE ./

RUN pip install --upgrade pip

COPY pystargazer ./pystargazer

COPY README.md setup.py ./

RUN pip install .

ENV PYTHONUNBUFFERED=1

CMD ["python", "-m", "pystargazer"]
