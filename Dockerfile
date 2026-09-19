FROM python:3.14.6-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && useradd --uid 10001 --create-home bot && mkdir /app/data && chown bot:bot /app/data
COPY tsue_bot ./tsue_bot
USER bot
CMD ["python", "-m", "tsue_bot"]
