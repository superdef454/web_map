# Gunicorn configuration file (gunicorn.conf.py)

import multiprocessing

# Server Socket
bind = '0.0.0.0:8002'  # Listen on all interfaces, port 8002
backlog = 2048  # Maximum pending connections

# Worker Processes
workers = multiprocessing.cpu_count() * 2 + 1  # Optimal worker count formula
worker_class = 'gthread'  # Use thread-based workers
threads = 4  # Number of threads per worker
max_requests = 1000  # Restart workers after this many requests
max_requests_jitter = 50  # Add randomness to prevent all workers restarting at once

# Timeouts
timeout = 3600  # Worker timeout (seconds)
graceful_timeout = 3600  # Timeout for graceful worker restart
keepalive = 30  # Keep-alive connection timeout (seconds)

# Security
limit_request_line = 4096  # Max size of HTTP request line
limit_request_fields = 100  # Max number of HTTP headers
limit_request_field_size = 8190  # Max size of each HTTP header

# Debugging
reload = False  # Never use auto-reload in production
spew = False  # Print every executed Python statement (dangerous!)

# Server Mechanics
preload_app = True  # Load application before forking workers
daemon = False  # Don't run in background (let supervisor handle this)

# Logging
accesslog = '-'  # Log to stdout
errorlog = '-'  # Log errors to stdout
loglevel = 'info'  # Log level
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s"'

# Process Naming
proc_name = 'web_map'  # Process name visible in ps/top