FROM python:3.12-slim
WORKDIR /app
COPY processor/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY processor/*.py ./
COPY ml/features.py ./
COPY ml/models/water_level_model.joblib ./model/water_level_model.joblib
ENV PYTHONUNBUFFERED=1
CMD ["python", "processor.py", "--host", "mosquitto", "--model", "/app/model/water_level_model.joblib"]