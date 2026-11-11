FROM python:3.13-slim
WORKDIR /app
COPY requirements.txt requirements.lock ./
RUN pip install --no-cache-dir -r requirements.txt \
    && useradd --uid 10001 --create-home bridge \
    && mkdir /app/.runs && chown bridge:bridge /app/.runs
COPY core ./core
COPY adapters ./adapters
COPY examples ./examples
COPY main.py ./main.py
USER bridge
ENV HB_BACKEND=fixture
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
