# Minimal non-root runner for throwaway Prove-It sandboxes.
FROM python:3.12-alpine

RUN adduser -D -u 10001 sandbox \
    && mkdir -p /work /tmp \
    && chown -R sandbox:sandbox /work /tmp

USER sandbox
WORKDIR /work

# No network tools needed; code is mounted at runtime as /work/user_code.py
CMD ["python", "/work/user_code.py"]
