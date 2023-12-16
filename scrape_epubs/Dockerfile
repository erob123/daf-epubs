FROM registry1.dso.mil/ironbank/opensource/python:v3.11.4

# runs this command to install chromedriver into docker layer: sudo apt-get install chromium-chromedriver
# this is needed for selenium to work
RUN apt-get update && apt-get install -y chromium-chromedriver

WORKDIR /home/python

COPY --chown=python:python  ./ ./
COPY --chown=python:python  .cache/python-packages ./python-packages

ENV PYTHONPATH=/home/python/app:/home/python/python-packages:/home/python/tests
ENV ENVIRONMENT=staging

CMD ["python", "main.py"]