FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && useradd --uid 10001 --create-home formacao
COPY server ./server
COPY *.html *.css *.js catalogo.json ./
COPY assets ./assets
COPY materiais ./materiais
RUN mkdir /data && chown formacao:formacao /data
USER formacao
ENV DATABASE_PATH=/data/formacao.sqlite3
EXPOSE 8080
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "2", "--timeout", "30", "--access-logfile", "-", "server.wsgi:application"]
