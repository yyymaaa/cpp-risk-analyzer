#include <iostream>
#include <fstream>
#include <string>
#include <clang-c/Index.h> 

CXChildVisitResult node_visitor(CXCursor cursor, CXCursor parent, CXClientData client_data) {
    CXSourceLocation location = clang_getCursorLocation(cursor);
    if (clang_Location_isInSystemHeader(location)) {
        return CXChildVisit_Recurse;
    }

    CXCursorKind kind = clang_getCursorKind(cursor);
    CXString name = clang_getCursorSpelling(cursor);
    std::string node_name = clang_getCString(name);
    clang_disposeString(name);

    // Filter 1: Inheritance relationships - High Risk
    if (kind == CXCursor_CXXBaseSpecifier) {
        std::cout << "  {\"type\": \"inheritance\", \"target\":\"" << node_name << "\"}," <<std::endl;
    }

    // Filter 2: Function call - Medium Risk
    else if (kind == CXCursor_CallExpr) {
        if (!node_name.empty()) {
            std::cout << "  {\"type\": \"function_call\", \"target\":\"" << node_name << "\"}," <<std::endl;
        }
    }
    return CXChildVisit_Recurse;
}

int main(int argc, char** argv) {
    if (argc < 2) {
        std::cerr << "Usage: ./semantic_parser <path_to_cpp_file>" << std::endl;
        return 1;
    }

    std::string file_path = argv[1];

    // Initialize the Clang compiler instance
    CXIndex index = clang_createIndex(0,0);

    const char* clang_args[] = {
        "-x", "c++",                                
        "-std=c++17",                              
        "-I/home/ojuka/Desktop/leveldb",            
        "-I/home/ojuka/Desktop/leveldb/include"     
    };
    int num_args = sizeof(clang_args) / sizeof(clang_args[0]);

    // Compile the target file into an AST in memory
    CXTranslationUnit unit = clang_parseTranslationUnit(
        index, 
        file_path.c_str(),
        clang_args, num_args,
        nullptr, 0,
        CXTranslationUnit_None
    );

    if (unit == nullptr) {
        std::cerr << "Error: Clang failed to parse " << file_path <<std::endl;
        return 1;
    }

    std::cout << "{" << std::endl;
    std::cout << "  \"file\": \"" << file_path << "\"," << std::endl;
    std::cout << "  \"dependencies\": [" << std::endl;

    // Get the root node of the AST and start traversa;
    CXCursor root_cursor = clang_getTranslationUnitCursor(unit);
    clang_visitChildren(root_cursor, node_visitor, nullptr);

    std::cout << "      {}"<< std::endl;
    std::cout << "  ]" << std::endl;
    std::cout << "}" << std::endl;

    clang_disposeTranslationUnit(unit);
    clang_disposeIndex(index);

    return 0;
}