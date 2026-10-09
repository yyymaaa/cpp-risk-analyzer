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
        """Create missing tables and migrate semantic columns without dropping data."""
        with self.connection.cursor() as cursor:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS structural_metrics (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    file_path VARCHAR(255) NOT NULL,
                    fan_in INT,
                    fan_out INT,
                    pagerank FLOAT,
                    betweenness FLOAT
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS semantic_dependencies (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    source_file VARCHAR(255) NOT NULL,
                    dependency_type VARCHAR(50),
                    target_name VARCHAR(255),
                    target_file VARCHAR(255) NULL,
                    resolution_status VARCHAR(30) NULL
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS commits (
                    commit_hash VARCHAR(64) PRIMARY KEY,
                    author VARCHAR(255),
                    timestamp BIGINT
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS commit_files (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    commit_hash VARCHAR(64),
                    file_path VARCHAR(255),
                    FOREIGN KEY (commit_hash)
                        REFERENCES commits(commit_hash) ON DELETE CASCADE
                )
            """)

            cursor.execute("SHOW COLUMNS FROM semantic_dependencies")
            columns = {row["Field"] for row in cursor.fetchall()}

            if "target_file" not in columns:
                cursor.execute("""
                    ALTER TABLE semantic_dependencies
                    ADD COLUMN target_file VARCHAR(255) NULL
                """)
            if "resolution_status" not in columns:
                cursor.execute("""
                    ALTER TABLE semantic_dependencies
                    ADD COLUMN resolution_status VARCHAR(30) NULL
                """)

        self.connection.commit()
        print("Database schema verified; existing records preserved.")

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
                        INSERT INTO semantic_dependencies
                            (source_file, dependency_type, target_name,
                             target_file, resolution_status)
                        VALUES (%s, %s, %s, %s, %s)
                    """, (
                        file_path,
                        dep.get("type", "unknown"),
                        dep.get("target", ""),
                        dep.get("target_file"),
                        dep.get("resolution_status")
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
                        SELECT %s, %s
                        WHERE NOT EXISTS (
                            SELECT 1 FROM commit_files
                            WHERE commit_hash = %s AND file_path = %s
                        )
                    """, (c_hash, file_path, c_hash, file_path))

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