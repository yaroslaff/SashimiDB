import os
import datetime

__version__='0.1'

started = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
docker_build_time = None
docker_build_time_path = '/app/docker-build-time.txt'

if os.path.exists(docker_build_time_path):
    with open(docker_build_time_path) as fh: 
        docker_build_time = fh.read().strip()

