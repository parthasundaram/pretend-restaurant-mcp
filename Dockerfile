FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY restaurant_server.py .
ENV PORT=8000 RESERVATIONS_DB=/data/reservations.sqlite3
RUN mkdir /data
EXPOSE 8000
CMD ["python", "restaurant_server.py"]
