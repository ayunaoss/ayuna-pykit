import asyncio
import hashlib
import logging
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from io import BytesIO
from typing import Annotated, Any, AsyncGenerator, Callable, List, Literal, Tuple, Union

from ayuna_core.basetypes import CoreData, ErrorOrBytesIO, ErrorOrStr, NonEmptyStr
from ayuna_creds.aws_config import CredConfig as AwsCredConfig
from ayuna_creds.azure_config import CredConfig as AzureCredConfig
from ayuna_creds.gcp_config import CredConfig as GcpCredConfig
from pydantic import AliasChoices, Field, HttpUrl, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

## NOTE: BulkPutEntry is used for `put_objects`
# It is a tuple of (key, data, overwrite)
BulkPutEntry = Tuple[str, BytesIO, bool]


class DoStoreEnv(BaseSettings):
    model_config = SettingsConfigDict(
        case_sensitive=True,
        env_file_encoding="utf-8",
        allow_inf_nan=False,
        populate_by_name=True,
        loc_by_alias=True,
    )

    cache_size: int = Field(
        validation_alias=AliasChoices("DOSTORE_CACHE_SIZE"), default=128, ge=1
    )
    cache_ttl_sec: int = Field(
        validation_alias=AliasChoices("DOSTORE_CACHE_TTL_SEC"), default=300, ge=10
    )
    concurrency: int = Field(
        validation_alias=AliasChoices("DOSTORE_CONCURRENCY"), default=16, ge=1
    )


__dostore_env: DoStoreEnv | None = None


def dostore_env():
    global __dostore_env

    if __dostore_env is None:
        __dostore_env = DoStoreEnv()

    return __dostore_env


class UnixFsDoStoreConfig(CoreData):
    typid: Literal["unix-fs"] = "unix-fs"
    sroot: NonEmptyStr
    is_readonly: bool = False

    @model_validator(mode="after")
    def check_sroot(self):
        if not self.sroot.startswith("/"):
            raise ValueError(f"Store's root folder path must be absolute: {self.sroot}")

        if self.sroot.endswith("/"):
            raise ValueError(
                f"Store's root folder path must not end with a slash: {self.sroot}"
            )

        return self


class AwsS3DoStoreConfig(CoreData):
    typid: Literal["aws-s3"] = "aws-s3"
    endpoint: NonEmptyStr = "s3.amazonaws.com"
    tls_enabled: bool = True
    check_certs: bool = True
    bucket_name: NonEmptyStr
    cred_config: AwsCredConfig


class AzureBlobDoStoreConfig(CoreData):
    typid: Literal["azure-blob"] = "azure-blob"
    account_url: HttpUrl
    container_name: NonEmptyStr
    connection_string: SecretStr | None = None
    cred_config: AzureCredConfig | None = None

    @model_validator(mode="after")
    def check_cred_config(self):
        if not self.connection_string and not self.cred_config:
            raise ValueError("Either connection_string or cred_config must be provided")

        return self


class GCSDoStoreConfig(CoreData):
    typid: Literal["gcp-storage"] = "gcp-storage"
    project_id: NonEmptyStr
    bucket_name: NonEmptyStr
    cred_config: GcpCredConfig


StoreConfig = Annotated[
    Union[
        UnixFsDoStoreConfig,
        AwsS3DoStoreConfig,
        AzureBlobDoStoreConfig,
        GCSDoStoreConfig,
    ],
    Field(discriminator="typid"),
]


class BaseDoStore(ABC):
    __store_env = dostore_env()
    _logger = logging.getLogger(__name__)

    @abstractmethod
    def __init__(self, config: StoreConfig, aio_loop: asyncio.AbstractEventLoop):
        self._aio_loop = aio_loop
        self._store_id = self._gen_store_id(config=config)
        self._thread_executor = ThreadPoolExecutor(
            max_workers=self.__store_env.concurrency,
            thread_name_prefix=f"store-{self._store_id}",
        )

    @property
    def store_id(self):
        return self._store_id

    def _gen_store_id(self, config: StoreConfig):
        config_bytes = config.model_dump_json().encode("utf-8")
        return hashlib.md5(config_bytes).hexdigest()

    def object_basename(self, key: str) -> str:
        return key.split("/")[-1]

    def object_dirname(self, key: str) -> str:
        return "/".join(key.split("/")[:-1])

    def add_thread_pool_task(self, func: Callable, *fargs, **fkwargs):
        """Run the function in the thread pool and return the result."""

        if not self._thread_executor:
            raise RuntimeError("Thread pool executor is not available")

        wrapped_fn = partial(func, *fargs, **fkwargs)
        return self._aio_loop.run_in_executor(self._thread_executor, wrapped_fn)

    @abstractmethod
    def object_store_path(self, key: str) -> str:
        """Compute the path of the object in the store."""
        raise NotImplementedError()

    @abstractmethod
    async def close(self):
        """Close the store."""
        await asyncio.sleep(0)

        if self._thread_executor:
            self._thread_executor.shutdown(wait=True)
            self._thread_executor = None

    @abstractmethod
    async def get_object(self, key: str) -> ErrorOrBytesIO:
        """Read the object from the store."""
        raise NotImplementedError()

    @abstractmethod
    async def put_object(
        self, key: str, data: BytesIO, overwrite: bool = False
    ) -> ErrorOrStr:
        """Write the object to the store."""
        raise NotImplementedError()

    @abstractmethod
    async def delete_object(self, key: str) -> ErrorOrStr:
        """Delete the object from the store."""
        raise NotImplementedError()

    @abstractmethod
    def get_objects(self, keys: List[str]) -> AsyncGenerator[ErrorOrBytesIO, None]:
        """
        Read the objects from the store.

        Parameters
        ----------
        keys : List[str]
            The keys of the objects to read.

        Returns
        -------
        AsyncGenerator[ErrorOrBytesIO, Any]
            The objects read from the store.
        """
        raise NotImplementedError()

    @abstractmethod
    def put_objects(
        self, entries: List[BulkPutEntry]
    ) -> AsyncGenerator[ErrorOrStr, Any]:
        """
        Write the objects to the store.

        Parameters
        ----------
        entries : List[BulkPutEntry]
            The objects to write.

        Returns
        -------
        AsyncGenerator[ErrorOrStr, Any]
            The results of the writes.
        """
        raise NotImplementedError()

    @abstractmethod
    def delete_objects(self, keys: List[str]) -> AsyncGenerator[ErrorOrStr, Any]:
        """
        Delete the objects from the store.

        Parameters
        ----------
        keys : List[str]
            The keys of the objects to delete.

        Returns
        -------
        AsyncGenerator[ErrorOrStr, Any]
            The results of the deletes.
        """
        raise NotImplementedError()

    @abstractmethod
    async def object_exists(self, key: str) -> bool:
        """Check if the object exists in the store."""
        raise NotImplementedError()

    @abstractmethod
    async def total_objects(self) -> int:
        """Get the total number of objects in the store."""
        raise NotImplementedError()

    @classmethod
    def create(
        cls,
        config: StoreConfig,
        aio_loop: asyncio.AbstractEventLoop,
    ) -> "BaseDoStore":
        """Factory method to create appropriate store instance based on config."""
        from .aws_s3 import AwsS3Store
        from .azure_blob import AzureBlobStore
        from .google_cs import GoogleCloudStore
        from .unix_fs import UnixFsStore

        store_map = {
            "unix-fs": UnixFsStore,
            "aws-s3": AwsS3Store,
            "azure-blob": AzureBlobStore,
            "gcp-storage": GoogleCloudStore,
        }

        store_class = store_map.get(config.typid)
        if store_class is None:
            raise ValueError(f"Unknown store type: {config.typid}")

        return store_class(config=config, aio_loop=aio_loop)
