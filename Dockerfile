FROM python:3.10-slim

WORKDIR /app
COPY . .

RUN pip install --no-cache-dir -r requirements_backend.txt \
    && pip install --no-cache-dir -r requirements_predict.txt \
    && pip install flask-cors

EXPOSE 7860
CMD ["python", "app_combined.py"]
