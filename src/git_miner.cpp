#include <iostream>
#include <git2.h>
#include <map>
#include <string>
#include <vector>

int main(int argc, char** argv) {
    if (argc < 2) {
        std::cerr << "Usage: ./git_miner <path_to_repo\n";
        return 1;
    }

    // Boot up the libgit2 backend
    git_libgit2_init();
    git_repository *repo = nullptr;

    // open the binary .git folder directly
    if (git_repository_open(&repo, argv[1]) != 0) {
        std::cerr << "Error: Could not open Git repository at " << argv[1] << "\n";
        return 1;
    }

    // Create a revision walker to travese history backwoards from HEAD
    git_revwalk *walker = nullptr;
    git_revwalk_new(&walker, repo);
    git_revwalk_sorting(walker, GIT_SORT_TIME);
    git_revwalk_push_head(walker);

    git_oid oid;
    std::cout << "[\n";
    bool first_commit = true;


    // Loop through every single commit in the repository's history
    while (git_revwalk_next(&oid, walker) == 0) {
        git_commit *commit = nullptr;
        if (git_commit_lookup(&commit, repo, &oid) == 0) {
            const git_signature *author = git_commit_author(commit);
            git_time_t time = git_commit_time(commit);

            char oid_str[GIT_OID_HEXSZ +1];
            git_oid_tostr(oid_str, sizeof(oid_str), &oid);

            std::vector<std::string> files;
            git_tree *tree = nullptr; 
            git_commit_tree(&tree, commit);

            git_commit *parent = nullptr;
            git_tree *parent_tree = nullptr;

            if (git_commit_parent(&parent, commit, 0) == 0) {
                git_commit_tree(&parent_tree, parent);
            }

            // calculate the diff between this commit and its parent
            git_diff *diff = nullptr;
            git_diff_tree_to_tree(&diff, repo, parent_tree, tree, nullptr);

            int num_deltas = git_diff_num_deltas(diff);
            for (int i = 0; i < num_deltas; i++) {
                const git_diff_delta *delta = git_diff_get_delta(diff, i);
                std::string path = delta->new_file.path;

                if (path.find(".cc") != std::string::npos ||
                    path.find(".h") != std::string::npos ||
                    path.find(".cpp") != std::string::npos) {
                        files.push_back(path);
                }
            }

            if (!files.empty()) {
                if (!first_commit) std::cout << ",\n";
                std::cout << "  {\n";
                std::cout << "    \"id\": \"" << oid_str << "\",\n";
                std::cout << "    \"author\": \"" << author->name << "\",\n";
                std::cout << "    \"timestamp\": " << time << ",\n";
                std::cout << "    \"files\": [";
                for (size_t i = 0; i < files.size(); i++) {
                    std::cout << "\"" << files[i] << "\"";
                    if (i < files.size() - 1) std::cout << ", ";
                }
                std::cout << "]\n  }";
                first_commit = false;
            }

            // manually free memory for this specific commit cycle
            git_diff_free(diff);
            git_tree_free(parent_tree);
            git_commit_free(parent);
            git_tree_free(tree);
            git_commit_free(commit);
        }
    }
    
    std::cout << "\n]\n";
    git_revwalk_free(walker);
    git_repository_free(repo);
    git_libgit2_shutdown();
    return 0;
}