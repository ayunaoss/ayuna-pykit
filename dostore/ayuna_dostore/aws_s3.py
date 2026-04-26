import asyncio
from io import BytesIO
from typing import Any, AsyncGenerator, List

from ayuna_core.basetypes import AyunaError, ErrorOrBytesIO, ErrorOrStr
from ayuna_creds.aws_provider import CredProvider
from botocore.exceptions import ClientError

from .base import AwsS3DoStoreConfig, BaseDoStore, BulkPutEntry


class AwsS3Store(BaseDoStore):
    """AWS S3 based DoStore implementation."""

    def __init__(
        self,
        *,
        config: AwsS3DoStoreConfig,
        aio_loop: asyncio.AbstractEventLoop,
    ):
        super().__init__(config, aio_loop)
        self._config = config

        cred_provider = CredProvider(config=config.cred_config)
        session = cred_provider.resolve_session()

        self._client = session.client(
            "s3",
            endpoint_url=(
                f"https://{config.endpoint}"
                if config.tls_enabled
                else f"http://{config.endpoint}"
            ),
            verify=config.check_certs,
        )

        # Ensure bucket exists or try to create it
        try:
            self._client.head_bucket(Bucket=config.bucket_name)
        except ClientError as e:
            err_code = e.response.get("Error", {}).get("Code")

            if err_code in ("404", "NoSuchBucket", "NotFound"):
                if config.cred_config.region:
                    self._client.create_bucket(
                        Bucket=config.bucket_name,
                        CreateBucketConfiguration={
                            "LocationConstraint": config.cred_config.region
                        },
                    )
                else:
                    self._client.create_bucket(Bucket=config.bucket_name)

                self._logger.info(f"Created bucket: {config.bucket_name}")
            else:
                raise

    def object_store_path(self, key: str):
        return f"{self._config.bucket_name}/{key}"

    async def close(self) -> None:
        await asyncio.sleep(0)
        self._logger.info(f"Closing {self._config.typid} store: {self._store_id}")
        await super().close()

    def __get_object(self, key: str):
        resp = self._client.get_object(Bucket=self._config.bucket_name, Key=key)

        try:
            data = resp["Body"].read()
        finally:
            try:
                resp["Body"].close()
            except Exception:
                pass

        return BytesIO(data)

    async def get_object(self, key: str) -> ErrorOrBytesIO:
        try:
            odata = await self.add_thread_pool_task(self.__get_object, key)

            if not isinstance(odata, BytesIO):
                raise TypeError(
                    f"Expected BytesIO from __get_object, got {type(odata)}"
                )

            return odata
        except Exception as ex:
            error_mesg = f"Failed to read object: {key} from {self._config.typid} store: {self._store_id} for bucket: {self._config.bucket_name}"
            self._logger.error(error_mesg, exc_info=ex)

            return AyunaError(error_mesg, exc_cause=ex)

    def __put_object(self, key: str, data: BytesIO, overwrite: bool = False):
        if not overwrite:
            try:
                self._client.head_object(Bucket=self._config.bucket_name, Key=key)
                return -1
            except ClientError as ex:
                code = ex.response.get("Error", {}).get("Code")

                if code not in ("404", "NoSuchKey", "NotFound"):
                    raise

        data.seek(0)
        data_len = data.getbuffer().nbytes

        self._client.put_object(
            Bucket=self._config.bucket_name,
            Key=key,
            Body=data,
            ContentLength=data_len,
            ContentType="application/octet-stream",
        )

        return data_len

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
            error_mesg = f"Failed to write object: {key} to {self._config.typid} store: {self._store_id} for bucket: {self._config.bucket_name}"
            self._logger.error(error_mesg, exc_info=ex)

            return AyunaError(error_mesg, exc_cause=ex)

    def __delete_object(self, key: str):
        self._client.delete_object(Bucket=self._config.bucket_name, Key=key)

    async def delete_object(self, key: str) -> ErrorOrStr:
        try:
            await self.add_thread_pool_task(self.__delete_object, key)

            return f"Deleted object: {key}"
        except Exception as ex:
            error_mesg = f"Failed to delete object: {key} from {self._config.typid} store: {self._store_id} for bucket: {self._config.bucket_name}"
            self._logger.error(error_mesg, exc_info=ex)

            return AyunaError(error_mesg, exc_cause=ex)

    async def get_objects(
        self, keys: List[str]
    ) -> AsyncGenerator[ErrorOrBytesIO, None]:
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

    def __object_exists(self, key: str) -> bool:
        try:
            obj_stat = self._client.head_object(
                Bucket=self._config.bucket_name, Key=key
            )
            self._logger.debug(
                f"Object: {key} exists in store: {self._store_id} for bucket: {self._config.bucket_name}, with stats: {obj_stat}"
            )

            return True
        except ClientError as ex:
            code = ex.response.get("Error", {}).get("Code")
            if code in ("404", "NoSuchKey", "NotFound"):
                self._logger.debug(
                    f"Object: {key} does not exist in store: {self._store_id} for bucket: {self._config.bucket_name}"
                )

                return False
            else:
                self._logger.error(
                    f"Failed to check if object: {key} exists in store: {self._store_id} for bucket: {self._config.bucket_name}"
                )

                raise

    async def object_exists(self, key: str) -> bool:
        return await self.add_thread_pool_task(self.__object_exists, key)

    def __total_objects(self) -> int:
        count = 0

        paginator = self._client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self._config.bucket_name):
            contents = page.get("Contents") or []
            count += len(contents)

        return count

    async def total_objects(self) -> int:
        return await self.add_thread_pool_task(self.__total_objects)
