
FROM endstone/endstone:latest

USER root

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libc++1 \
        libc++abi1 \
        libunwind-14 \
    && rm -rf /var/lib/apt/lists/*
