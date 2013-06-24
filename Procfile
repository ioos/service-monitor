web: gunicorn app:app -b 0.0.0.0:$PORT -w 2
rq_stats: rqworker -c ioos_service_monitor.defaults stats
rq_scheduler: ./scheduler

