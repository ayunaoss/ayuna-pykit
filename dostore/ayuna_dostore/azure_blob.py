import asyncio
from io import BytesIO
from typing import Any, AsyncGenerator, List

from ayuna_core.basetypes import AyunaError, ErrorOrBytesIO, ErrorOrStr
from ayuna_creds.azure_provider import CredProvider
from azure.core.credentials import AzureKeyCredential
from azure.core.exceptions import ResourceExistsError, ResourceNotFoundError
from azure.storage.blob.aio import BlobClient, BlobServiceClient, ContainerClient

from .base import AzureBlobDoStoreConfig, BaseDoStore, BulkPutEntry


class AzureBlobStore(BaseDoStore):
    """Azure Blob Storage based DoStore implementation."""

    def __init__(
        self,
        *,
        config: AzureBlobDoStoreConfig,
        aio_loop: asyncio.AbstractEventLoop,
    ):
        super().__init__(config, aio_loop)
        self._config = config
        self._service_client: BlobServiceClient | None = None
        self._container_client: ContainerClient | None = None
        self._initialized = False

    async def _ensure_initialized(self) -> None:
        """Lazy initialization of Azure clients."""
        if self._initialized:
            return

        try:
            if not self._config.cred_config:
                if self._config.connection_string is None:
                    raise ValueError(
                        "connection_string is required when cred_config is not provided"
                    )

                self._service_client = BlobServiceClient.from_connection_string(
                    conn_str=self._config.connection_string.get_secret_value()
                )
            else:
                cred_provider = CredProvider(config=self._config.cred_config)
                credential = cred_provider.resolve_credential(async_mode=True)

                if isinstance(credential, AzureKeyCredential):
                    raise ValueError(
                        "AzureKeyCredential is not supported for BlobServiceClient initialization"
                    )

                self._service_client = BlobServiceClient(
                    account_url=str(self._config.account_url),
                    credential=credential,
                )

            self._container_client = await self._ensure_container()
            self._initialized = True
        except Exception as ex:
            self._logger.error(
                f"Failed to initialize store: {self._store_id} for container: {self._config.container_name}",
                exc_info=ex,
            )
            raise AyunaError(f"Failed to initialize store: {self._store_id}") from ex

        if not self._container_client:
            await self._service_client.close()
            raise AyunaError(f"Failed to initialize store: {self._store_id}")

    async def _ensure_container(self) -> ContainerClient | None:
        if self._service_client is None:
            return None

        container_client: ContainerClient | None = None
        service_client = self._service_client  # Help type checker

        try:
            container_client = service_client.get_container_client(
                container=self._config.container_name
            )
            # Check if container exists by calling get_container_properties
            await container_client.get_container_properties()
        except ResourceNotFoundError:
            try:
                container_client = await service_client.create_container(
                    name=self._config.container_name
                )
                self._logger.info(f"Created container: {self._config.container_name}")
            except ResourceExistsError:
                # Race condition: container was created between check and creation
                container_client = service_client.get_container_client(
                    container=self._config.container_name
                )
        except Exception as ex:
            self._logger.error(
                f"Failed to ensure container: {self._config.container_name} in store: {self._store_id}",
                exc_info=ex,
            )
            return None

        return container_client

    def object_store_path(self, key: str) -> str:
        return f"{self._config.container_name}/{key}"

    async def close(self) -> None:
        await asyncio.sleep(0)
        self._logger.info(f"Closing {self._config.typid} store: {self._store_id}")

        if self._container_client:
            await self._container_client.close()
            self._container_client = None

        if self._service_client:
            await self._service_client.close()
            self._service_client = None

        await super().close()

    async def get_object(self, key: str) -> ErrorOrBytesIO:
        await self._ensure_initialized()

        try:
            if self._container_client is None:
                raise RuntimeError(f"Store {self._store_id} is not initialized")

            blob_client = self._container_client.get_blob_client(blob=key)
            stream_dl = await blob_client.download_blob()
            odata = await stream_dl.readall()

            await blob_client.close()

            return BytesIO(odata)
        except Exception as ex:
            error_mesg = f"Failed to read object: {key} from {self._config.typid} store: {self._store_id} for container: {self._config.container_name}"

            self._logger.error(error_mesg, exc_info=ex)
            return AyunaError(error_mesg, exc_cause=ex)

    async def put_object(
        self, key: str, data: BytesIO, overwrite: bool = False
    ) -> ErrorOrStr:
        await self._ensure_initialized()

        blob_client: BlobClient | None = None

        try:
            if self._container_client is None:
                raise RuntimeError(f"Store {self._store_id} is not initialized")

            blob_client = self._container_client.get_blob_client(blob=key)
            ul_result = await blob_client.upload_blob(
                data.getvalue(), overwrite=overwrite
            )

            self._logger.debug(ul_result)
            return f"Written {data.getbuffer().nbytes} bytes for object: {key}"
        except ResourceExistsError:
            return AyunaError(
                f"Object: {key} already exists in store: {self._store_id}"
            )
        except Exception as ex:
            error_mesg = f"Failed to write object: {key} to {self._config.typid} store: {self._store_id} for container: {self._config.container_name}"

            self._logger.error(error_mesg, exc_info=ex)
            return AyunaError(error_mesg, exc_cause=ex)
        finally:
            if blob_client:
                await blob_client.close()

    async def delete_object(self, key: str) -> ErrorOrStr:
        await self._ensure_initialized()

        blob_client: BlobClient | None = None

        try:
            if self._container_client is None:
                raise RuntimeError(f"Store {self._store_id} is not initialized")

            blob_client = self._container_client.get_blob_client(blob=key)
            await blob_client.delete_blob()
            await blob_client.close()

            return f"Deleted object: {key}"
        except Exception as ex:
            error_mesg = f"Failed to delete object: {key} from {self._config.typid} store: {self._store_id} for container: {self._config.container_name}"

            self._logger.error(error_mesg, exc_info=ex)
            return AyunaError(error_mesg, exc_cause=ex)
        finally:
            if blob_client:
                await blob_client.close()

    async def get_objects(self, keys: List[str]) -> AsyncGenerator[ErrorOrBytesIO, Any]:
        if not keys:
            yield AyunaError("Keys list is empty")
            return

        for okey in keys:
            result = await self.get_object(key=okey)
            yield result

    async def put_objects(
        self, entries: List[BulkPutEntry]
    ) -> AsyncGenerator[ErrorOrStr, Any]:
        if not entries:
            yield AyunaError("Entries list is empty")
            return

        for okey, data, overwrite in entries:
            result = await self.put_object(key=okey, data=data, overwrite=overwrite)
            yield result

    async def delete_objects(self, keys: List[str]) -> AsyncGenerator[ErrorOrStr, Any]:
        if not keys:
            yield AyunaError("Keys list is empty")
            return

        for okey in keys:
            result = await self.delete_object(key=okey)
            yield result

    async def object_exists(self, key: str) -> bool:
        await self._ensure_initialized()

        if self._container_client is None:
            raise RuntimeError(f"Store {self._store_id} is not initialized")

        blob_client = self._container_client.get_blob_client(blob=key)

        try:
            blob_exists = await blob_client.exists()
            return blob_exists
        finally:
            await blob_client.close()

    async def total_objects(self) -> int:
        await self._ensure_initialized()

        if self._container_client is None:
            raise RuntimeError(f"Store {self._store_id} is not initialized")

        count = 0
        async for _ in self._container_client.list_blobs():
            count += 1

        return count
