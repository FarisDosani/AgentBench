FROM python:3.11-slim

WORKDIR /workspace

RUN pip install --no-cache-dir pytest

CMD ["python", "-c", "print('AgentBench container ready')"]
