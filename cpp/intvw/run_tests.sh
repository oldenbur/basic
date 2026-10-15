#!/bin/bash

set -euo pipefail
set -x

cmake -S . -B build-llvm -G Ninja \
  -DCMAKE_C_COMPILER=/opt/homebrew/opt/llvm/bin/clang \
  -DCMAKE_CXX_COMPILER=/opt/homebrew/opt/llvm/bin/clang++ \
  -DCMAKE_EXPORT_COMPILE_COMMANDS=ON

echo "Build succeeded"

cmake --build build-llvm --target practice_test && \
  ./build-llvm/tests/practice_test
