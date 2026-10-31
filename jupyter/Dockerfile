FROM quay.io/jupyter/scipy-notebook:2024-10-28

# --- L1-L3: aceleasi biblioteci ca in versiunea 1.0 -----------------------
RUN pip install --no-cache-dir \
      "psycopg[binary]==3.2.3" \
      "pgvector==0.3.6" \
      "boto3==1.35.54" \
      "qdrant-client==1.12.1" \
      "pillow==11.0.0" \
      "imagehash==4.3.1" \
      "opencv-python-headless==4.10.0.84" \
      "tqdm==4.67.0"

# --- L4: indecsi aproximativi ---------------------------------------------
RUN pip install --no-cache-dir "faiss-cpu==1.9.0.post1"

# --- L5, L7: encoderul CLIP, doar pe CPU ----------------------------------
# PyTorch din indexul CPU: fara el, pip aduce varianta CUDA (cativa GB in plus).
RUN pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu \
      "torch==2.5.1" "torchvision==0.20.1" && \
    pip install --no-cache-dir "open_clip_torch==2.29.0"

# Modelul se descarca O DATA, la construire, si ramane in imagine.
# In laborator reteaua nu e necesara (HF_HUB_OFFLINE=1).
ENV HF_HOME=/opt/hf
USER root
RUN mkdir -p /opt/hf && chown -R ${NB_UID}:${NB_GID} /opt/hf
USER ${NB_UID}
RUN python -c "import open_clip; open_clip.create_model_and_transforms('ViT-B-32', pretrained='laion2b_s34b_b79k'); open_clip.get_tokenizer('ViT-B-32')"
ENV HF_HUB_OFFLINE=1
