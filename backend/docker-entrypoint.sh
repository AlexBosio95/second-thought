#!/bin/sh
set -eu
chown app:app /data
exec su -s /bin/sh app -c 'exec uvicorn app.main:app --host 0.0.0.0 --port 8000'
