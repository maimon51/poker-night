# Use the slim variant of Python to reduce base image size
FROM python:3.10 as builder

# Install dependencies for Poetry and any required libraries
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl libgl1-mesa-glx && \
    curl -sSL https://install.python-poetry.org | python3 - && \
    apt-get purge -y --auto-remove curl && \
    rm -rf /var/lib/apt/lists/*

# Disable creation of a virtual environment
ENV POETRY_VIRTUALENVS_CREATE=false

# Set the working directory
WORKDIR /app

# Copy only essential files for dependency installation
COPY pyproject.toml poetry.lock ./ 

RUN /root/.local/bin/poetry install --no-root --no-dev && \
    # Remove unnecessary to reduce image size
    rm -rf ~/.cache/pip  \
    /app/.venv \
    /root/.cache \
    /root/.local \
    /usr/local/lib/python3.10/site-packages/pandas \
    /usr/local/lib/python3.10/site-packages/scipy* \
    /usr/local/lib/python3.10/site-packages/nvidia/cudnn/lib/libcudnn_graph.so.9 \ 
    /usr/local/lib/python3.10/site-packages/nvidia/cudnn/lib/libcudnn_ops.so.9 \ 
    /usr/local/lib/python3.10/site-packages/nvidia/cudnn/lib/libcudnn_adv.so.9 \ 
    /usr/local/lib/python3.10/site-packages/nvidia/cudnn/lib/libcudnn_heuristic.so.9 \ 
    /usr/local/lib/python3.10/site-packages/nvidia/cudnn/lib/libcudnn_engines_runtime_compiled.so.9 \ 
    /usr/local/lib/python3.10/site-packages/nvidia/cudnn/lib/libcudnn_engines_precompiled.so.9 \ 
    /usr/local/lib/python3.10/site-packages/nvidia/cudnn/lib/libcudnn_cnn.so.9 \ 
    /usr/local/lib/python3.10/site-packages/nvidia/nvtx/lib/libnvToolsExt.so.1 \ 
    /usr/local/lib/python3.10/site-packages/nvidia/cusolver/lib/libcusolver.so.11 \ 
    /usr/local/lib/python3.10/site-packages/nvidia/cusolver/lib/libcusolverMg.so.11 \ 
    /usr/local/lib/python3.10/site-packages/nvidia/cufft/lib/libcufftw.so.11 \ 
    /usr/local/lib/python3.10/site-packages/nvidia/cublas/lib/libnvblas.so.12 \ 
    /usr/local/lib/python3.10/site-packages/nvidia/cuda_cupti/lib/libnvperf_target.so \ 
    /usr/local/lib/python3.10/site-packages/nvidia/cuda_cupti/lib/libpcsamplingutil.so \ 
    /usr/local/lib/python3.10/site-packages/nvidia/cuda_cupti/lib/libnvperf_host.so \ 
    /usr/local/lib/python3.10/site-packages/nvidia/cuda_cupti/lib/libcheckpoint.so \ 
    /usr/local/lib/python3.10/site-packages/nvidia/cuda_nvrtc/lib/libnvrtc-builtins.so.12.4 \ 
    /usr/local/lib/python3.10/site-packages/nvidia/cuda_nvrtc/lib/libnvrtc.so.12 \
    /usr/local/lib/python3.10/site-packages/torch/lib/libtorch_cuda_linalg.so \
    /usr/local/lib/python3.10/site-packages/triton && \
    find /usr/local/lib/python3.10 -depth -name "include"  -exec rm -rf {} \; && \
    find /usr/local/lib/python3.10 -depth -name "tests"  -exec rm -rf {} \; && \
    find /usr/local/lib/python3.10 -name "*.pyc" -delete && \
    find /usr/local/lib/python3.10 -name "*.pyo" -delete && \
    find /usr/local/lib/python3.10 -name "*.txt" -delete && \
    find /usr/local/lib/python3.10 -name "*.exe" -delete && \
    find /usr/local/lib/python3.10 -name INSTALLER -delete && \
    find /usr/local/lib/python3.10 -name RECORD -delete && \
    find /usr/local/lib/python3.10 -name LICENSE -delete && \
    find /usr/local/lib/python3.10 -name WHEEL  -delete && \
    find /usr/local -depth -name "__pycache__ "  -exec rm -rf {} \; && \
    find /usr/local -depth -name "fonts"  -exec rm -rf {} \; && \
    find /usr/local -depth -name "images"  -exec rm -rf {} \;

COPY . .

# Final image without build dependencies
FROM python:3.10-slim
WORKDIR /app

# Copy only necessary files and dependencies from the builder
RUN echo "Size of /usr/local/lib:" && du -sh /usr/local/lib/
COPY --from=builder /usr/local/lib/python3.10/site-packages /usr/local/lib/python3.10/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
RUN echo "Size of /usr/local/lib:" && du -sh /usr/local/lib/
COPY --from=builder /app/bot.py /app/yolov8s_playing_cards-1.pt /app/
COPY --from=builder /usr/lib/x86_64-linux-gnu/gconv /usr/lib/x86_64-linux-gnu/
COPY --from=builder /usr/lib/x86_64-linux-gnu/ld-linux-x86-64.so.2 /usr/lib/x86_64-linux-gnu/
COPY --from=builder /usr/lib/x86_64-linux-gnu/libGL.so.1.7.0 /usr/lib/x86_64-linux-gnu/
COPY --from=builder /usr/lib/x86_64-linux-gnu/libGLX.so.0.0.0 /usr/lib/x86_64-linux-gnu/
COPY --from=builder /usr/lib/x86_64-linux-gnu/libGLdispatch.so.0.0.0 /usr/lib/x86_64-linux-gnu/
COPY --from=builder /usr/lib/x86_64-linux-gnu/libX11.so.6.4.0 /usr/lib/x86_64-linux-gnu/
COPY --from=builder /usr/lib/x86_64-linux-gnu/libXau.so.6.0.0 /usr/lib/x86_64-linux-gnu/
COPY --from=builder /usr/lib/x86_64-linux-gnu/libXau.so.6 /usr/lib/x86_64-linux-gnu/
COPY --from=builder /usr/lib/x86_64-linux-gnu/libXdmcp.so.6.0.0 /usr/lib/x86_64-linux-gnu/
COPY --from=builder /usr/lib/x86_64-linux-gnu/libXdmcp.so.6 /usr/lib/x86_64-linux-gnu/
COPY --from=builder /usr/lib/x86_64-linux-gnu/libbsd.so.0.11.7 /usr/lib/x86_64-linux-gnu/
COPY --from=builder /usr/lib/x86_64-linux-gnu/libbsd.so.0 /usr/lib/x86_64-linux-gnu/
COPY --from=builder /usr/lib/x86_64-linux-gnu/libbz2.so.1.0.4 /usr/lib/x86_64-linux-gnu/
COPY --from=builder /usr/lib/x86_64-linux-gnu/libc.so.6 /usr/lib/x86_64-linux-gnu/
COPY --from=builder /usr/lib/x86_64-linux-gnu/libcrypto.so.3 /usr/lib/x86_64-linux-gnu/
COPY --from=builder /usr/lib/x86_64-linux-gnu/libdl.so.2 /usr/lib/x86_64-linux-gnu/
COPY --from=builder /usr/lib/x86_64-linux-gnu/libffi.so.8.1.2 /usr/lib/x86_64-linux-gnu/
COPY --from=builder /usr/lib/x86_64-linux-gnu/libfribidi.so.0.4.0 /usr/lib/x86_64-linux-gnu/
COPY --from=builder /usr/lib/x86_64-linux-gnu/libgcc_s.so.1 /usr/lib/x86_64-linux-gnu/
COPY --from=builder /usr/lib/x86_64-linux-gnu/libglib-2.0.so.0.7400.6 /usr/lib/x86_64-linux-gnu/
COPY --from=builder /usr/lib/x86_64-linux-gnu/libgthread-2.0.so.0.7400.6 /usr/lib/x86_64-linux-gnu/
COPY --from=builder /usr/lib/x86_64-linux-gnu/liblzma.so.5.4.1 /usr/lib/x86_64-linux-gnu/
COPY --from=builder /usr/lib/x86_64-linux-gnu/libm.so.6 /usr/lib/x86_64-linux-gnu/
COPY --from=builder /usr/lib/x86_64-linux-gnu/libmd.so.0.0.5 /usr/lib/x86_64-linux-gnu/
COPY --from=builder /usr/lib/x86_64-linux-gnu/libpcre2-8.so.0.11.2 /usr/lib/x86_64-linux-gnu/
COPY --from=builder /usr/lib/x86_64-linux-gnu/libpthread.so.0 /usr/lib/x86_64-linux-gnu/
COPY --from=builder /usr/lib/x86_64-linux-gnu/librt.so.1 /usr/lib/x86_64-linux-gnu/
COPY --from=builder /usr/lib/x86_64-linux-gnu/libssl.so.3 /usr/lib/x86_64-linux-gnu/
COPY --from=builder /usr/lib/x86_64-linux-gnu/libstdc++.so.6.0.30 /usr/lib/x86_64-linux-gnu/
COPY --from=builder /usr/lib/x86_64-linux-gnu/libutil.so.1 /usr/lib/x86_64-linux-gnu/
COPY --from=builder /usr/lib/x86_64-linux-gnu/libuuid.so.1.3.0 /usr/lib/x86_64-linux-gnu/
COPY --from=builder /usr/lib/x86_64-linux-gnu/libxcb.so.1.1.0 /usr/lib/x86_64-linux-gnu/
COPY --from=builder /usr/lib/x86_64-linux-gnu/libxcb.so.1 /usr/lib/x86_64-linux-gnu/
COPY --from=builder /usr/lib/x86_64-linux-gnu/libz.so.1.2.13 /usr/lib/x86_64-linux-gnu/
COPY --from=builder /usr/lib/x86_64-linux-gnu/libGL.so.1 /usr/lib/x86_64-linux-gnu/
COPY --from=builder /usr/lib/x86_64-linux-gnu/libGLX.so.0 /usr/lib/x86_64-linux-gnu/
COPY --from=builder /usr/lib/x86_64-linux-gnu/libGLdispatch.so.0 /usr/lib/x86_64-linux-gnu
COPY --from=builder /usr/lib/x86_64-linux-gnu/libgthread-2.0.so.0 /usr/lib/x86_64-linux-gnu/libgthread-2.0.so.0
COPY --from=builder /usr/lib/x86_64-linux-gnu/libglib-2.0.so.0 /usr/lib/x86_64-linux-gnu/libglib-2.0.so.0
COPY --from=builder /usr/lib/x86_64-linux-gnu/libX11.so.6 /usr/lib/x86_64-linux-gnu/libX11.so.6

# Run the bot
CMD ["python", "bot.py"]
