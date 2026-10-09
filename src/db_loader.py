import json
import pymysql
from pathlib import Path

class DatabaseLoader:
    def __init__(self, db_name="cpp_risk_analyzer", user="root", config_path="db_config.json"):
        password = ""
        if Path(config_path).exists():
            with open(config_path, "r") as f:
                config = json.load(f)
                password = config.get("password", "")
        else:
            print(f"Warning: {config_path} not found. Attempting connection without password.")

        self.connection = pymysql.connect(
            host="localhost",
            user=user,
            password=password,
            database=db_name,
            charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor
        )
        self.create_tables()

    def create_tables(self):
        with self.connection.cursor() as cursor:
            # Drop old tables to ensure a clean slate on re-runs
            cursor.execute("DROP TABLE IF EXISTS commit_files;")
            cursor.execute("DROP TABLE IF EXISTS commits;")
            cursor.execute("DROP TABLE IF EXISTS semantic_dependencies;")
            cursor.execute("DROP TABLE IF EXISTS structural_metrics;")

            # 1. Structural Metrics Table
            cursor.execute("""
                CREATE TABLE structural_metrics (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    file_path VARCHAR(255) NOT NULL,
                    fan_in INT,
                    fan_out INT,
                    pagerank FLOAT,
                    betweenness FLOAT
                );
            """)

            # 2. Semantic Dependencies Table
            cursor.execute("""
                CREATE TABLE semantic_dependencies (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    source_file VARCHAR(255) NOT NULL,
                    dependency_type VARCHAR(50),
                    target_name VARCHAR(255)
                );
            """)

            # 3. Commits Table
            cursor.execute("""
                CREATE TABLE commits (
                    commit_hash VARCHAR(64) PRIMARY KEY,
                    author VARCHAR(255),
                    timestamp BIGINT
                );
            """)

            # 4. Commit-Files Relationship Table (Enables fast co-change queries)
            cursor.execute("""
                CREATE TABLE commit_files (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    commit_hash VARCHAR(64),
                    file_path VARCHAR(255),
                    FOREIGN KEY (commit_hash) REFERENCES commits(commit_hash) ON DELETE CASCADE
                );
            """)
        self.connection.commit()
        print("Database schema successfully created in MariaDB.")

    def load_structural_data(self, json_path="structural_metrics.json"):
        if not Path(json_path).exists():
            print(f"Skipping {json_path}: file not found.")
            return
        
        with open(json_path, "r") as f:
            data = json.load(f)

        with self.connection.cursor() as cursor:
            for file_path, metrics in data.items():
                cursor.execute("""
                    INSERT INTO structural_metrics (file_path, fan_in, fan_out, pagerank, betweenness)
                    VALUES (%s, %s, %s, %s, %s)
                """, (
                    file_path,
                    metrics.get("fan_in", 0),
                    metrics.get("fan_out", 0),
                    metrics.get("pagerank", 0.0),
                    metrics.get("betweenness", 0.0)
                ))
        self.connection.commit()
        print("Loaded structural metrics into MySQL.")

    def load_semantic_data(self, json_path="semantic_dependencies.json"):
        if not Path(json_path).exists():
            print(f"Skipping {json_path}: file not found.")
            return

        with open(json_path, "r") as f:
            data = json.load(f)

        with self.connection.cursor() as cursor:
            for file_path, deps in data.items():
                for dep in deps:
                    cursor.execute("""
                        INSERT INTO semantic_dependencies (source_file, dependency_type, target_name)
                        VALUES (%s, %s, %s)
                    """, (
                        file_path,
                        dep.get("type", "unknown"),
                        dep.get("target", "")
                    ))
        self.connection.commit()
        print("Loaded semantic dependencies into MySQL.")

    def load_git_data(self, json_path="commit_log.json"):
        if not Path(json_path).exists():
            print(f"Skipping {json_path}: file not found.")
            return

        with open(json_path, "r") as f:
            commits = json.load(f)

        with self.connection.cursor() as cursor:
            for commit in commits:
                c_hash = commit.get("id")
                author = commit.get("author")
                timestamp = commit.get("timestamp")
                files = commit.get("files", [])

                # Insert commit metadata
                cursor.execute("""
                    INSERT IGNORE INTO commits (commit_hash, author, timestamp)
                    VALUES (%s, %s, %s)
                """, (c_hash, author, timestamp))
                
                # Insert relational mapping for files touched in this commit
                for file_path in files:
                    cursor.execute("""
                        INSERT INTO commit_files (commit_hash, file_path)
                        VALUES (%s, %s)
                    """, (c_hash, file_path))

        self.connection.commit()
        print("Loaded Git commit logs and file mappings into MySQL.")

    def close(self):
        self.connection.close()

if __name__ == "__main__":
    loader = DatabaseLoader()
    loader.load_structural_data()
    loader.load_semantic_data()
    loader.load_git_data()
    loader.close()
    print("Database ingestion complete!")