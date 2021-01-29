FROM python:3.9-slim-buster

RUN apt update
RUN apt install --yes fontconfig poppler-utils libusb-1.0 fonts-dejavu git

RUN mkdir /code
WORKDIR /code
COPY . /code

RUN pip install -r requirements.txt

CMD ["./run.py", "--port", "8099", "--model", "PT-P700", "--default-label-size", "12"]