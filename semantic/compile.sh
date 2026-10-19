#!/bin/bash
g++ -O3 -std=c++17 src/semantic_parser.cpp -o src/semantic_parser -lclang
echo "Semantic Parser compiled successfully!"