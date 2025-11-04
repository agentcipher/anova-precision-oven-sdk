FROM python:3.11-slim

WORKDIR /app

# Install dependencies
RUN pip install --no-cache-dir .

# Copy application
COPY anova_oven_cli.py .
COPY settings.yaml .

# Create logs directory
RUN mkdir -p logs

CMD ["python", "anova_oven_cli.py", "discover"]