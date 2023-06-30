FROM tiangolo/uvicorn-gunicorn-fastapi:python3.11

COPY ./docker/requirements.txt /app/requirements.txt

RUN pip install --no-cache-dir --upgrade -r /app/requirements.txt
RUN mkdir /data

COPY ./docker/tires.json /data/tires.json
COPY exact.py /app/main.py
COPY ./docker/exact.yml /etc/exact.yml
COPY ./docker/start.sh /
RUN date > /app/docker-build-time.txt

# COPY exact.yml /app/ 


