FROM tiangolo/uvicorn-gunicorn-fastapi:python3.11

COPY ./docker/requirements.txt /app/requirements.txt

RUN pip install --no-cache-dir --upgrade -r /app/requirements.txt

RUN date > /app/docker-build-time.txt

COPY exact.py /app/main.py
COPY ./docker/exact-docker.yml /etc/exact.yml
COPY ./docker/start.sh /
# COPY exact.yml /app/ 


