#include <git2.h>
#include <algorithm>
#include <iostream>
#include <set>
#include <string>
#include <vector>

static std::string json_escape(const char* input) {
    std::string out;
    if (!input) return out;

    for (const unsigned char* p =
             reinterpret_cast<const unsigned char*>(input); *p; ++p) {
        switch (*p) {
            case '"':  out += "\\\""; break;
            case '\\': out += "\\\\"; break;
            case '\b': out += "\\b"; break;
            case '\f': out += "\\f"; break;
            case '\n': out += "\\n"; break;
            case '\r': out += "\\r"; break;
            case '\t': out += "\\t"; break;
            default:
                if (*p < 0x20) {
                    const char hex[] = "0123456789abcdef";
                    out += "\\u00";
                    out += hex[*p >> 4];
                    out += hex[*p & 0x0f];
                } else {
                    out += static_cast<char>(*p);
                }
        }
    }
    return out;
}

static bool is_cpp_file(const std::string& path) {
    const auto dot = path.find_last_of('.');
    if (dot == std::string::npos) return false;

    const std::string ext = path.substr(dot);
    return ext == ".cc" || ext == ".cpp" || ext == ".cxx" ||
           ext == ".h" || ext == ".hh" || ext == ".hpp" ||
           ext == ".hxx";
}

int main(int argc, char** argv) {
    if (argc < 2) {
        std::cerr << "Usage: ./git_miner <path_to_repo>\n";
        return 1;
    }

    git_libgit2_init();

    git_repository* repo = nullptr;
    if (git_repository_open(&repo, argv[1]) != 0) {
        const git_error* error = git_error_last();
        std::cerr << "Could not open repository: "
                  << (error ? error->message : "unknown error") << "\n";
        git_libgit2_shutdown();
        return 1;
    }

    git_revwalk* walker = nullptr;
    if (git_revwalk_new(&walker, repo) != 0 ||
        git_revwalk_sorting(walker, GIT_SORT_TIME) != 0 ||
        git_revwalk_push_head(walker) != 0) {
        const git_error* error = git_error_last();
        std::cerr << "Could not initialize revision walk: "
                  << (error ? error->message : "unknown error") << "\n";
        if (walker) git_revwalk_free(walker);
        git_repository_free(repo);
        git_libgit2_shutdown();
        return 1;
    }

    git_oid oid;
    bool first_commit = true;
    std::cout << "[\n";

    while (git_revwalk_next(&oid, walker) == 0) {
        git_commit* commit = nullptr;
        if (git_commit_lookup(&commit, repo, &oid) != 0) continue;

        const git_signature* author = git_commit_author(commit);
        const git_time_t timestamp = git_commit_time(commit);

        git_tree* tree = nullptr;
        git_tree* parent_tree = nullptr;
        git_commit* parent = nullptr;
        git_diff* diff = nullptr;

        int rc = git_commit_tree(&tree, commit);
        if (rc == 0 && git_commit_parentcount(commit) > 0 &&
            git_commit_parent(&parent, commit, 0) == 0) {
            git_commit_tree(&parent_tree, parent);
        }

        // A null parent tree represents the empty tree for the root commit.
        if (rc == 0) {
            rc = git_diff_tree_to_tree(&diff, repo, parent_tree, tree, nullptr);
        }

        if (rc != 0) {
            const git_error* error = git_error_last();
            std::cerr << "Warning: diff failed for a commit: "
                      << (error ? error->message : "unknown error") << "\n";
        } else {
            std::set<std::string> changed_files;

            for (size_t i = 0; i < git_diff_num_deltas(diff); ++i) {
                const git_diff_delta* delta = git_diff_get_delta(diff, i);
                if (!delta) continue;

                // Keep the old path for deletions/renames and the new path
                // for additions/renames, so both affected paths are retained.
                if (delta->status != GIT_DELTA_ADDED &&
                    is_cpp_file(delta->old_file.path)) {
                    changed_files.insert(delta->old_file.path);
                }
                if (delta->status != GIT_DELTA_DELETED &&
                    is_cpp_file(delta->new_file.path)) {
                    changed_files.insert(delta->new_file.path);
                }
            }

            // Commits without relevant C++ changes are intentionally excluded.
            if (!changed_files.empty()) {
                char oid_str[GIT_OID_HEXSZ + 1];
                git_oid_tostr(oid_str, sizeof(oid_str), &oid);

                if (!first_commit) std::cout << ",\n";
                first_commit = false;

                std::cout << "  {\n"
                          << "    \"id\": \"" << oid_str << "\",\n"
                          << "    \"author\": \"" 
                          << json_escape(author ? author->name : "") << "\",\n"
                          << "    \"timestamp\": " << timestamp << ",\n"
                          << "    \"files\": [";

                bool first_file = true;
                for (const auto& file : changed_files) {
                    if (!first_file) std::cout << ", ";
                    first_file = false;
                    std::cout << "\"" << json_escape(file.c_str()) << "\"";
                }
                std::cout << "]\n  }";
            }
        }

        if (diff) git_diff_free(diff);
        if (parent_tree) git_tree_free(parent_tree);
        if (parent) git_commit_free(parent);
        if (tree) git_tree_free(tree);
        git_commit_free(commit);
    }

    std::cout << "\n]\n";

    git_revwalk_free(walker);
    git_repository_free(repo);
    git_libgit2_shutdown();
    return 0;
}
