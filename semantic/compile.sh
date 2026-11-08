#!/bin/bash
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
g++ -O3 -std=c++17 "$SCRIPT_DIR/semantic_parser.cpp" -o "$SCRIPT_DIR/semantic_parser" -lclang || exit 1
echo "Semantic Parser compiled successfully!"