# Ayuna Pykit

A collection of Python libraries from Ayuna IO. Each of the libraries is summarized below.

1. **ayuna-core**: Python library providing core functionalities such as multi-process logger, crypto utilities, ssl contexts for client and server, json-rpc implementation, compression, date-time, string convertion utilities and OTEL telemetry classes. This library serves as a base for rest of the python libraries and applications within the AyunaIO ecosystem.
2. **ayuna-creds**: Python library providing cloud-provider credential classes to be used for various client connections to cloud services from AWS, Azure and GCP.
3. **ayuna-secrets**: Python library providing key-vault and secret-manager factory implementations for cloud providers such as AWS, Azure and GCP for secrets management. It also provides a local, yaml based secret file support with encrypted secret values.
4. **ayuna-dostore**: Python library providing file/object store management classes for cloud providers such as AWS, Azure and GCP along with local, Unix filesystem based storage support.

## Publishing

See `scripts/pypi-publishing.md` for PyPI/TestPyPI publishing setup and release workflow usage.
