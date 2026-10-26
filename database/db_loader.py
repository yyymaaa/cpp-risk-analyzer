import json
import sys
import pymysql
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

class DatabaseLoader:
    """Manages database schema initialization and ingestion of metrics, semantic dependencies, and Git logs into MySQL
    """
    def __init__(self, db_name="cpp_risk_analyzer", user="root", config_path=None):
        """initializes the DatabaseLoader and connects to the MySQL server

        Args:
            db_name (str, optional): Name of the MySQL database. Defaults to "cpp_risk_analyzer".
            user (str, optional): Database username. Defaults to "root".
            config_path (str, optional): Path to the database configuration JSON file. Defaults to "data/configuration/db_config.json".
        """
        if config_path is None:
            config_path = PROJECT_ROOT / "data" / "configuration" / "db_config.json"
        else:
            config_path = Path(config_path)

        password = ""
        if config_path.exists():
            with open(config_path, "r", encoding="utf-8") as f:
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

            for table in ["structural_metrics", "semantic_dependencies", "commits", "commit_files"]:
                cursor.execute(f"SHOW COLUMNS FROM {table}")
                cols = {row["Field"] for row in cursor.fetchall()}
                if "repo_name" not in cols:
                    cursor.execute(f"ALTER TABLE {table} ADD COLUMN repo_name VARCHAR(255) NOT NULL DEFAULT 'default'")

        self.connection.commit()
        # print("Database schema verified; repository multi-tenancy enabled.")

        self.connection.commit()
        # print("Database schema verified; existing records preserved.")

    def load_structural_data(self, json_path: Path | str, repo_name: str | None = None):
        """Loads graph structural metrics from a JSON file into MySQL

        Args:
            json_path (str, optional): Path to the structural metrics JSON file. Defaults to "data/extraction_output/structural_metrics.json".
        """     
        json_path = Path(json_path)
        if not json_path.exists():
            print(f"Skipping {json_path}: file not found.")
            return

        if repo_name is None:
            repo_name = json_path.stem.replace("_structural_metrics", "")

        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        with self.connection.cursor() as cursor:
            for file_path, metrics in data.items():
                cursor.execute("""
                    INSERT INTO structural_metrics (repo_name, file_path, fan_in, fan_out, pagerank, betweenness)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (
                    repo_name,
                    file_path,
                    metrics.get("fan_in", 0),
                    metrics.get("fan_out", 0),
                    metrics.get("pagerank", 0.0),
                    metrics.get("betweenness", 0.0)
                ))
        self.connection.commit()
        # print(f"Loaded structural metrics for '{repo_name}' into MySQL.")

    def load_semantic_data(self, json_path="data/extraction_output/semantic_dependencies.json"):
        """loads semantic dependency data from a JSON file into MySQL

        Args:
            json_path (str, optional): Path to the semantic dependencies JSON file. Defaults to "data/extraction_output/semantic_dependencies.json".
        """        
        json_path = Path(json_path)
        if not json_path.exists():
            print(f"Skipping {json_path}: file not found.")
            return

        if repo_name is None:
            repo_name = json_path.stem.replace("_semantic_dependencies", "")

        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        with self.connection.cursor() as cursor:
            for file_path, deps in data.items():
                for dep in deps:
                    cursor.execute("""
                        INSERT INTO semantic_dependencies
                            (repo_name, source_file, dependency_type, target_name, target_file, resolution_status)
                        VALUES (%s, %s, %s, %s, %s, %s)
                    """, (
                        repo_name,
                        file_path,
                        dep.get("type", "unknown"),
                        dep.get("target", ""),
                        dep.get("target_file"),
                        dep.get("resolution_status")
                    ))

        self.connection.commit()
        # print(f"Loaded semantic dependencies for '{repo_name}' into MySQL.")

    def load_git_data(self, json_path: Path | str, repo_name: str | None = None):
        """Loads Git commit history and touched file mappings from a JSON file into MySQL

        Args:
            json_path (str, optional): Path to the commit log JSON file. Defaults to "data/extraction_output/commit_log.json".
        """        
        json_path = Path(json_path)
        if not json_path.exists():
            print(f"Skipping {json_path}: file not found.")
            return

        if repo_name is None:
            repo_name = json_path.stem.replace("_commit_log", "")

        with open(json_path, "r", encoding="utf-8") as f:
            commits = json.load(f)

        with self.connection.cursor() as cursor:
            for commit in commits:
                c_hash = commit.get("id")
                author = commit.get("author")
                timestamp = commit.get("timestamp")
                files = commit.get("files", [])

                cursor.execute("""
                    INSERT IGNORE INTO commits (commit_hash, repo_name, author, timestamp)
                    VALUES (%s, %s, %s, %s)
                """, (c_hash, repo_name, author, timestamp))

                for file_path in files:
                    cursor.execute("""
                        INSERT INTO commit_files (repo_name, commit_hash, file_path)
                        SELECT %s, %s, %s
                        WHERE NOT EXISTS (
                            SELECT 1 FROM commit_files
                            WHERE commit_hash = %s AND file_path = %s AND repo_name = %s
                        )
                    """, (repo_name, c_hash, file_path, c_hash, file_path, repo_name))

        self.connection.commit()
        # print(f"Loaded Git commit logs for '{repo_name}' into MySQL.")

    def close(self):
        """Closes the active database connection
        """        
        self.connection.close()

if __name__ == "__main__":
    loader = DatabaseLoader()
    loader.close()