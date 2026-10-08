#include <iostream>
#include <git2.h>
#include <map>
#include <string>

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
    std::map<std::string, int> file_churn;

    // Loop through every single commit in the repository's history
    while (git_revwalk_next(&oid, walker) == 0) {
        git_commit *commit = nullptr;
        if (git_commit_lookup(&commit, repo, &oid) == 0) {
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
                        file_churn[path]++;
                }
            }

            // manually free memory for this specific commit cycle
            git_diff_free(diff);
            git_tree_free(parent_tree);
            git_commit_free(parent);
            git_tree_free(tree);
            git_commit_free(commit);
        }
    }

    // clean the core git structures
    git_revwalk_free(walker);
    git_repository_free(repo);
    git_libgit2_shutdown();

    // output the compiled Churn metrics as JSON
    std::cout << "{\n \"churn\": {\n";
    bool first = true;
    for (auto const& [file, count] : file_churn) {
        if (!first) std::cout << ",\n";
        std::cout << "  \"" << file << "\": " << count;
        first = false;
    }
    std::cout << "\n }\n}\n";

    return 0;
}