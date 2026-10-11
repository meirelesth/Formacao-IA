FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt && useradd -u 10001 -m finance
COPY financeiro /app/financeiro
RUN mkdir /data && chown finance:finance /data
USER finance
EXPOSE 8090
CMD ["gunicorn","--bind","0.0.0.0:8090","--workers","2","--timeout","30","--access-logfile","/dev/null","financeiro.app:wsgi"]
