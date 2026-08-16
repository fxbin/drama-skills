# Seedance adapter

Adapter command:

```json
{"command": ["python3", "/absolute/path/provider_adapters.py", "seedance"], "timeout_seconds": 3600}
```

Required environment:

- `ARK_API_KEY`: Volcengine Ark API key.
- `SEEDANCE_MODEL`: the exact enabled model/endpoint ID. There is intentionally no model default; in particular the
  adapter never assumes Seedance 2.0.

Optional environment:

- `SEEDANCE_BASE_URL` (default `https://ark.cn-beijing.volces.com/api/v3`)
- `SEEDANCE_POLL_INTERVAL` (default `5` seconds)
- `SEEDANCE_TIMEOUT_SECONDS` (default `1800` seconds)

The job must have modality `video` and exactly one `.mp4` output. Supported public parameters are `duration` (the
bundled safety envelope is 1–15 seconds) and `ratio` (`adaptive`, `1:1`, `3:4`, `4:3`, `9:16`, `16:9`, or `21:9`).
They are compiled into the documented prompt switches `--dur` and `--ratio`, not sent as unverified top-level fields.
The configured model/endpoint may support a narrower subset; account/model availability remains a runtime concern.
The bundled runtime adapter currently supports text-to-video only. Local references fail closed because the public video
contract does not prove that a local data URL is accepted. A deployment that needs image-to-video must add an external,
authorized upload step and call `compile_seedance_payload` with the resulting HTTPS or `asset://` URI; do not put a
temporary provider URL into the creator project.

The adapter creates an asynchronous task, polls `GET /contents/generations/tasks/{id}` until a terminal state, and
downloads `content.video_url` into a private temporary directory. Any unknown status fails closed.

Protocol reference: [Volcengine video generation API](https://www.volcengine.com/docs/82379/1520757).
