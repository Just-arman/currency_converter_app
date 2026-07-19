FROM python:3.13-slim

WORKDIR /currency_converter

COPY requirements.txt .

RUN pip install -r requirements.txt

COPY . .

RUN find docker -type f -name "*.sh" -exec sed -i 's/\r$//' {} \;
RUN chmod +x docker/entrypoint.sh

CMD ["./docker/entrypoint.sh"]