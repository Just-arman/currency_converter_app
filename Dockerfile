FROM python:3.13-slim

WORKDIR /currency_converter

COPY requirements.txt .

RUN pip install -r requirements.txt

COPY . .

RUN chmod +x docker/entrypoint.sh

# CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
CMD ["./docker/entrypoint.sh"]
