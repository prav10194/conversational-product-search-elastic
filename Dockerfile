FROM python:3.12-slim
WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app app
COPY templates templates
COPY static static
COPY data data
ENV PORT=8080
EXPOSE 8080
RUN useradd -u 10001 web && chown -R web /srv
USER web
CMD ["sh", "-c", "gunicorn -w 2 -b 0.0.0.0:${PORT} app.main:app"]
