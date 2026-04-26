#!/usr/bin/env bash

set -euo pipefail

REPOSITORY="${1:-pypi}"

if [[ "${REPOSITORY}" != "pypi" && "${REPOSITORY}" != "testpypi" ]]; then
  printf "Usage: %s [pypi|testpypi]\n" "$0"
  exit 1
fi

if ! command -v uv >/dev/null 2>&1; then
  printf "uv is required but not found in PATH\n"
  exit 1
fi

if ! command -v twine >/dev/null 2>&1; then
  printf "twine is required but not found in PATH\n"
  printf "Install it with: uv tool install twine\n"
  exit 1
fi

for package_dir in core creds secrets dostore; do
  rm -rf "${package_dir}/dist"
  (cd "${package_dir}" && uv build)
done

twine check core/dist/* creds/dist/* secrets/dist/* dostore/dist/*

twine upload --repository "${REPOSITORY}" core/dist/*
twine upload --repository "${REPOSITORY}" creds/dist/*
twine upload --repository "${REPOSITORY}" secrets/dist/*
twine upload --repository "${REPOSITORY}" dostore/dist/*

printf "Published packages to %s\n" "${REPOSITORY}"
