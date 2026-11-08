#!/bin/bash
# Script directory resolution
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

echo "Compiling C++ Git Miner binary..."
g++ -O3 -std=c++17 "$SCRIPT_DIR/git_miner.cpp" -o "$SCRIPT_DIR/git_miner" -lgit2

if [ $? -eq 0 ]; then
    echo "Git Miner compiled successfully at $SCRIPT_DIR/git_miner!"
else
    echo "Compilation failed. Ensure libgit2-devel is installed (e.g. sudo dnf install libgit2-devel)"
fi