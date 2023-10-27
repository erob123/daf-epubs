FROM registry1.dso.mil/ironbank/opensource/python:v3.11.4

WORKDIR /home/python

COPY --chown=python:python  ./ ./
COPY --chown=python:python  .cache/python-packages ./python-packages

ENV PYTHONPATH=/home/python/app:/home/python/python-packages:/home/python/tests
ENV ENVIRONMENT=staging

CMD ["python", "main.py"]