FROM mcr.microsoft.com/playwright/python:v1.47.0-noble


ENV PYTHONDONTWRITEBYTECODE=1 
ENV PYTHONUNBUFFERED=1        


WORKDIR /app


RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    sudo \
    passwd \
    && rm -rf /var/lib/apt/lists/*


RUN addgroup --system appgroup \
    && adduser --system --ingroup appgroup --disabled-password appuser \
    && echo "appuser:test" | chpasswd \
    && echo "appuser ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers


COPY requirements.txt .


RUN pip install --upgrade pip \
    && pip install -r requirements.txt


COPY . .

RUN chown -R appuser:appgroup /app


EXPOSE 8000


RUN playwright install


CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]


USER appuser
