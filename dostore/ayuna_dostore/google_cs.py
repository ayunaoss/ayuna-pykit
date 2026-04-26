import asyncio
from io import BytesIO
from typing import Any, AsyncGenerator, List

from ayuna_core.basetypes import AyunaError, ErrorOrBytesIO, ErrorOrStr
from ayuna_creds.gcp_provider import CredProvider
from google.api_core.exceptions import Conflict, NotFound
from google.cloud import storage

from .base import BaseDoStore, BulkPutEntry, GCSDoStoreConfig


class GoogleCloudStore(BaseDoStore):
    """Google Cloud Storage based DoStore implementation."""

    def __init__(
        self,
        *,
        config: GCSDoStoreConfig,
        aio_loop: asyncio.AbstractEventLoop,
    ):
        super().__init__(config, aio_loop)
        self._config = config

        cred_provider = CredProvider(config=self._config.cred_config)
        credentials = cred_provider.resolve_credentials()

        self._client = storage.Client(
            project=self._config.project_id, credentials=credentials
        )

        # Ensure bucket exists or create it
        try:
            self._bucket = self._client.get_bucket(config.bucket_name)
        except NotFound:
            self._logger.info(f"Bucket {config.bucket_name} not found. Creating...")
            try:
                self._bucket = self._client.create_bucket(config.bucket_name)
                self._logger.info(f"Created bucket: {config.bucket_name}")
            except Conflict:
                # Race condition safety
                self._bucket = self._client.get_bucket(config.bucket_name)

    def object_store_path(self, key: str):
        return f"{self._config.bucket_name}/{key}"

    async def close(self) -> None:
        await asyncio.sleep(0)
        self._logger.info(f"Closing {self._config.typid} store: {self._store_id}")

        self._client.close()
        await super().close()

    # ---------------- Internal blocking helpers ---------------- #

    def __get_object(self, key: str):
        blob = self._bucket.blob(key)

        try:
            data = blob.download_as_bytes()
            return BytesIO(data)
        except NotFound:
            raise FileNotFoundError(f"Object not found: {key}")

    async def get_object(self, key: str) -> ErrorOrBytesIO:
        try:
            odata = await self.add_thread_pool_task(self.__get_object, key)

            if not isinstance(odata, BytesIO):
                raise TypeError(
                    f"Expected BytesIO from __get_object, got {type(odata)}"
                )

            return odata
        except Exception as ex:
            error_mesg = (
                f"Failed to read object: {key} from {self._config.typid} store: "
                f"{self._store_id} for bucket: {self._config.bucket_name}"
            )
            self._logger.error(error_mesg, exc_info=ex)
            return AyunaError(error_mesg, exc_cause=ex)

    def __put_object(self, key: str, data: BytesIO, overwrite: bool = False):
        blob = self._bucket.blob(key)

        if not overwrite and blob.exists():
            return -1

        data.seek(0)
        data_bytes = data.read()

        blob.upload_from_string(
            data_bytes,
            content_type="application/octet-stream",
        )

        return len(data_bytes)

    async def put_object(
        self, key: str, data: BytesIO, overwrite: bool = False
    ) -> ErrorOrStr:
        try:
            result = await self.add_thread_pool_task(
                self.__put_object, key, data, overwrite
            )

            if not isinstance(result, int):
                raise TypeError(f"Expected int from __put_object, got {type(result)}")

            if result == -1:
                return AyunaError(
                    f"Object: {key} already exists in store: {self._store_id}"
                )

            return f"Written {result} bytes for object: {key}"
        except Exception as ex:
            error_mesg = (
                f"Failed to write object: {key} to {self._config.typid} store: "
                f"{self._store_id} for bucket: {self._config.bucket_name}"
            )
            self._logger.error(error_mesg, exc_info=ex)
            return AyunaError(error_mesg, exc_cause=ex)

    def __delete_object(self, key: str):
        blob = self._bucket.blob(key)
        blob.delete()

    async def delete_object(self, key: str) -> ErrorOrStr:
        try:
            await self.add_thread_pool_task(self.__delete_object, key)
            return f"Deleted object: {key}"
        except Exception as ex:
            error_mesg = (
                f"Failed to delete object: {key} from {self._config.typid} store: "
                f"{self._store_id} for bucket: {self._config.bucket_name}"
            )
            self._logger.error(error_mesg, exc_info=ex)
            return AyunaError(error_mesg, exc_cause=ex)

    # ---------------- Bulk APIs ---------------- #

    async def get_objects(
        self, keys: List[str]
    ) -> AsyncGenerator[ErrorOrBytesIO, None]:
        if not keys:
            yield AyunaError("Keys list is empty")
            return

        for k in keys:
            yield await self.get_object(k)

    async def put_objects(
        self, entries: List[BulkPutEntry]
    ) -> AsyncGenerator[ErrorOrStr, Any]:
        if not entries:
            yield AyunaError("Entries list is empty")
            return

        for key, data, overwrite in entries:
            yield await self.put_object(key=key, data=data, overwrite=overwrite)

    async def delete_objects(self, keys: List[str]) -> AsyncGenerator[ErrorOrStr, Any]:
        if not keys:
            yield AyunaError("Keys list is empty")
            return

        for k in keys:
            yield await self.delete_object(k)

    # ---------------- Misc APIs ---------------- #

    def __object_exists(self, key: str) -> bool:
        blob = self._bucket.blob(key)
        exists = blob.exists()

        if exists:
            self._logger.debug(
                f"Object: {key} exists in store: {self._store_id} "
                f"for bucket: {self._config.bucket_name}"
            )
        else:
            self._logger.debug(
                f"Object: {key} does not exist in store: {self._store_id} "
                f"for bucket: {self._config.bucket_name}"
            )

        return exists

    async def object_exists(self, key: str) -> bool:
        return await self.add_thread_pool_task(self.__object_exists, key)

    def __total_objects(self) -> int:
        count = 0

        for _ in self._client.list_blobs(self._config.bucket_name):
            count += 1

        return count

    async def total_objects(self) -> int:
        return await self.add_thread_pool_task(self.__total_objects)
