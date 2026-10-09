FROM python:3.12-slim
WORKDIR /app
COPY requirements-server.txt .
RUN pip install --no-cache-dir -r requirements-server.txt \
    && useradd --create-home --uid 10001 privsig
COPY privsig ./privsig
USER privsig
EXPOSE 10000
CMD ["python", "-m", "privsig.server.hosted"]
