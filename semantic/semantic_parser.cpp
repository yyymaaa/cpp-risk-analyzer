#include <clang-c/Index.h>
#include <filesystem>
#include <iostream>
#include <string>
#include <vector>

struct Dependency {
    std::string type;
    std::string target;
    std::string target_file;
};

static std::string to_string(CXString value) {
    const char* text = clang_getCString(value);
    std::string result = text ? text : "";
    clang_disposeString(value);
    return result;
}

static std::string json_escape(const std::string& value) {
    std::string out;

    for (unsigned char c : value) {
        switch (c) {
            case '"':  out += "\\\""; break;
            case '\\': out += "\\\\"; break;
            case '\b': out += "\\b";  break;
            case '\f': out += "\\f";  break;
            case '\n': out += "\\n";  break;
            case '\r': out += "\\r";  break;
            case '\t': out += "\\t";  break;
            default:
                if (c < 0x20) {
                    const char hex[] = "0123456789abcdef";
                    out += "\\u00";
                    out += hex[(c >> 4) & 0xf];
                    out += hex[c & 0xf];
                } else {
                    out += static_cast<char>(c);
                }
        }
    }

    return out;
}

static std::string declaration_file(CXCursor declaration) {
    if (clang_Cursor_isNull(declaration)) {
        return "";
    }

    CXSourceLocation location = clang_getCursorLocation(declaration);
    CXFile file = nullptr;
    clang_getFileLocation(location, &file, nullptr, nullptr, nullptr);

    if (!file) {
        return "";
    }

    return to_string(clang_getFileName(file));
}

struct ParseContext {
    std::string source_file;
    std::vector<Dependency>* dependencies;
};

static std::string cursor_file(CXCursor cursor) {
    CXSourceLocation location = clang_getCursorLocation(cursor);
    CXFile file = nullptr;

    clang_getFileLocation(
        location, &file, nullptr, nullptr, nullptr
    );

    if (!file) {
        return "";
    }

    return to_string(clang_getFileName(file));
}

static CXChildVisitResult node_visitor(
    CXCursor cursor,
    CXCursor parent,
    CXClientData client_data
) {
    auto* context = static_cast<ParseContext*>(client_data);

    const std::string current_file = cursor_file(cursor);

    if (current_file.empty()) {
        return CXChildVisit_Recurse;
    }

    if (std::filesystem::weakly_canonical(current_file) !=
        std::filesystem::weakly_canonical(context->source_file)) {
        return CXChildVisit_Recurse;
    }

    auto* dependencies = context->dependencies;

    CXCursorKind kind = clang_getCursorKind(cursor);
    CXCursor declaration = clang_getNullCursor();
    std::string dependency_type;

    if (kind == CXCursor_CXXBaseSpecifier) {
        dependency_type = "inheritance";

        // Resolve the base type to its declaration.
        CXType base_type = clang_getCursorType(cursor);
        declaration = clang_getTypeDeclaration(base_type);

        if (clang_Cursor_isNull(declaration)) {
            declaration = clang_getCursorReferenced(cursor);
        }
    } else if (kind == CXCursor_CallExpr) {
        dependency_type = "function_call";

        // Resolve the call to the referenced function/method.
        declaration = clang_getCursorReferenced(cursor);
    } else {
        return CXChildVisit_Recurse;
    }

    std::string target = to_string(clang_getCursorSpelling(declaration));

    // Keep unresolved dependencies visible instead of inventing a file.
    if (target.empty()) {
        target = to_string(clang_getCursorSpelling(cursor));
    }

    if (target.empty()) {
        return CXChildVisit_Recurse;
    }

    Dependency dependency{
        dependency_type,
        target,
        declaration_file(declaration)
    };

    dependencies->push_back(dependency);
    return CXChildVisit_Recurse;
}

int main(int argc, char** argv) {
    if (argc < 3) {
        std::cerr
            << "Usage: semantic_parser <cpp_file> <repository_root>\n";
        return 1;
    }

    const std::string file_path = argv[1];
    const std::string repository_root = argv[2];
    const std::string include_root = repository_root + "/include";

    CXIndex index = clang_createIndex(0, 0);

    const char* clang_args[] = {
        "-x", "c++",
        "-std=c++17",
        "-I", repository_root.c_str(),
        "-I", include_root.c_str()
    };

    CXTranslationUnit unit = clang_parseTranslationUnit(
        index,
        file_path.c_str(),
        clang_args,
        sizeof(clang_args) / sizeof(clang_args[0]),
        nullptr,
        0,
        CXTranslationUnit_None
    );

    if (!unit) {
        std::cerr << "Clang failed to parse: " << file_path << '\n';
        clang_disposeIndex(index);
        return 1;
    }

    std::vector<Dependency> dependencies;

    ParseContext context{
        std::filesystem::weakly_canonical(file_path).string(),
        &dependencies
    };

    CXCursor root = clang_getTranslationUnitCursor(unit);
    clang_visitChildren(root, node_visitor, &context);

    std::cout << "{\n";
    std::cout << "  \"file\": \"" << json_escape(file_path) << "\",\n";
    std::cout << "  \"dependencies\": [";

    for (std::size_t i = 0; i < dependencies.size(); ++i) {
        const auto& dep = dependencies[i];

        std::cout << (i == 0 ? "\n" : ",\n");
        std::cout << "    {"
                  << "\"type\": \"" << json_escape(dep.type) << "\", "
                  << "\"target\": \"" << json_escape(dep.target) << "\", "
                  << "\"target_file\": ";

        if (dep.target_file.empty()) {
            std::cout << "null";
        } else {
            std::cout << "\"" << json_escape(dep.target_file) << "\"";
        }

        std::cout << "}";
    }

    if (!dependencies.empty()) {
        std::cout << '\n';
        std::cout << "  ";
    }

    std::cout << "]\n}\n";

    clang_disposeTranslationUnit(unit);
    clang_disposeIndex(index);

    return 0;
}