FROM python:3.8.2-slim

MAINTAINER LightQuantum

WORKDIR /app

RUN pip install --upgrade pip

COPY ./requirements.txt ./requirements.txt

RUN pip install -r requirements.txt

COPY pystargazer ./pystargazer

ENV PYTHONUNBUFFERED=1

CMD ["python", "-m", "pystargazer"]
