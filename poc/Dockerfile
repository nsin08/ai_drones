FROM python:3.11-slim

WORKDIR /app

# Copy requirements and install dependencies
COPY poc/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend code
COPY poc/ .

# Copy built UI
COPY ui/dist /app/ui/dist

EXPOSE 5000
CMD ["python", "mission_control_v3.py"]
