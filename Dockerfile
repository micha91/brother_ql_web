FROM python:3.6-slim-buster

RUN apt update
RUN apt install --yes fontconfig poppler-utils libusb-1.0
RUN pip install brother_ql Flask flask_bootstrap4 qrcode pdf2image brother-label-printer

RUN mkdir /code
WORKDIR /code
COPY . /code

CMD ["/code/run.py", "--port", "6060", "--model", "PT-P700", "--default-label-size", "12"]