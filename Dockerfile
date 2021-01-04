FROM python:3-alpine

WORKDIR /usr/src/app

ENV DOCKER 1

COPY requirements.txt ./
RUN pip3 install --no-cache-dir -r requirements.txt

COPY main.py .

CMD [ "python3", "./main.py" ]
