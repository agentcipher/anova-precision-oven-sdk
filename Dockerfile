FROM python:3.11-slim

COPY pyproject.toml /tmp

RUN cd /tmp && \
    apt update && \
    apt -y upgrade  && \
    apt -y install --no-install-recommends openssh-client && \
    pip --no-cache-dir install uv && \
    uv pip install --system --no-cache-dir . && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* && \
    rm -f pyproject.toml

# RUN useradd -u ${UID} -m -s /bin/bash ${LOGNAME}
WORKDIR /app

CMD ["/bin/bash"]