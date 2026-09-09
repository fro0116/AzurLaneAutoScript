# syntax=docker/dockerfile:1.4
# docker build -t hgjazhgj/alas:latest .
# docker run -v ${PWD}:/app/AzurLaneAutoScript -p 22212:22212 --name alas -it --rm hgjazhgj/alas

# Native arm64 needs source builds for some old scientific packages, so keep
# expensive steps split into cacheable layers.
ARG ALAS_DOCKER_PLATFORM=linux/arm64
FROM --platform=${ALAS_DOCKER_PLATFORM} python:3.7-slim-bullseye
ARG WATCHEXEC_VERSION=2.5.1

WORKDIR /app/AzurLaneAutoScript

COPY requirements.txt /tmp/requirements.txt

# Initial download of UiAutomator2 is slow outside of China using appetizer mirror, switch to GitHub
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
    adb \
    build-essential \
    ca-certificates \
    curl \
    gfortran \
    git \
    libavcodec-dev \
    libavdevice-dev \
    libavfilter-dev \
    libavformat-dev \
    libavutil-dev \
    libgomp1 \
    liblapack-dev \
    libopenblas-dev \
    libswresample-dev \
    libswscale-dev \
    openssh-client \
    pkg-config \
 && rm -rf /var/lib/apt/lists/*

RUN git config --global --add safe.directory '*'

RUN set -eux; \
    arch="$(dpkg --print-architecture)"; \
    case "${arch}" in \
      amd64) watchexec_arch="x86_64-unknown-linux-musl" ;; \
      arm64) watchexec_arch="aarch64-unknown-linux-musl" ;; \
      *) echo "Unsupported architecture for watchexec: ${arch}" >&2; exit 1 ;; \
    esac; \
    curl -fsSL -o /tmp/watchexec.deb \
      "https://github.com/watchexec/watchexec/releases/download/v${WATCHEXEC_VERSION}/watchexec-${WATCHEXEC_VERSION}-${watchexec_arch}.deb"; \
    apt-get update; \
    apt-get install -y --no-install-recommends /tmp/watchexec.deb; \
    rm -f /tmp/watchexec.deb; \
    rm -rf /var/lib/apt/lists/*

RUN --mount=type=cache,target=/root/.cache/pip \
    pip install Cython==0.29.37

RUN --mount=type=cache,target=/root/.cache/pip \
    pip install av==10.0.0 --no-build-isolation

RUN --mount=type=cache,target=/root/.cache/pip \
    pip install numpy==1.16.6

RUN --mount=type=cache,target=/root/.cache/pip \
    pip install pybind11==2.4.3

ENV FFLAGS="-fallow-argument-mismatch" \
    FCFLAGS="-fallow-argument-mismatch"

RUN --mount=type=cache,target=/root/.cache/pip \
    pip install scipy==1.4.1 --no-build-isolation

RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r /tmp/requirements.txt \
 && rm /tmp/requirements.txt

# PyPI mxnet 1.6.0 has no usable arm64 libmxnet.so.
RUN --mount=type=cache,target=/root/.cache/pip \
    case "$(uname -m)" in \
      aarch64|arm64) \
        pip uninstall -y mxnet \
     && pip install https://raw.githubusercontent.com/binss/python-wheel/main/mxnet-1.9.1-py3-none-any.whl \
        ;; \
    esac

# Runtime libs required by the custom arm64 MXNet wheel.
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
    libatlas3-base \
    libopencv-imgcodecs4.5 \
 && rm -rf /var/lib/apt/lists/*

ENV LD_LIBRARY_PATH=/usr/local/mxnet \
    MXNET_LIBRARY_PATH=/usr/local/mxnet/libmxnet.so

CMD ["watchexec", "--restart", "--poll", "2s", "--debounce", "1s", "--exts", "py,json,yaml,yml,toml,txt,html,css,js,ts,vue,png,jpg,jpeg,gif", "--watch", "alas.py", "--watch", "gui.py", "--watch", "module", "--watch", "campaign", "--watch", "assets", "--watch", "webapp", "--ignore", "**/.git/**", "--ignore", "**/__pycache__/**", "--ignore", "**/.pytest_cache/**", "--ignore", "**/.mypy_cache/**", "--ignore", "**/.ruff_cache/**", "--ignore", "**/.cache/**", "--ignore", "log/**", "--ignore", "logs/**", "--ignore", "tmp/**", "--ignore", "temp/**", "--", "python", "gui.py", "--host", "127.0.0.1", "--port", "22212"]
