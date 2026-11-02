FROM python:3.12-slim
WORKDIR /app
RUN pip install --no-cache-dir "paho-mqtt>=2.0,<3"
COPY simulator/*.py ./
ENV PYTHONUNBUFFERED=1
CMD ["python", "simulator.py", "--host", "mosquitto"]