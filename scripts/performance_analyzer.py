#!/usr/bin/env python
"""
Database Performance Analyzer

This script helps identify slow queries and suggests database optimizations for FreelanceFlow.
It works with both SQLite (development) and PostgreSQL (production).

Usage:
    python -m scripts.performance_analyzer --log-file app.log [--suggest-indexes] [--verbose]
"""

import argparse
import os
import re
import sqlite3
import statistics
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

import pandas as pd
import sqlparse
from dotenv import load_dotenv

# Try to import psycopg2 for PostgreSQL analysis
try:
    import psycopg2
    import psycopg2.extras
    HAS_POSTGRES = True
except ImportError:
    HAS_POSTGRES = False


class PerformanceAnalyzer:
    """Analyzes database performance and suggests optimizations."""

    def __init__(self, db_url: str, verbose: bool = False):
        """Initialize the analyzer with the database URL."""
        self.db_url = db_url
        self.verbose = verbose
        self.queries = []
        self.table_columns = {}
        self.slow_queries = []
        self.query_frequencies = Counter()
        
        # Connect to the appropriate database
        if db_url.startswith('sqlite:///'):
            self.db_type = 'sqlite'
            db_path = db_url.replace('sqlite:///', '')
            self.conn = sqlite3.connect(db_path)
            self.conn.row_factory = sqlite3.Row
        elif db_url.startswith('postgresql://') and HAS_POSTGRES:
            self.db_type = 'postgresql'
            self.conn = psycopg2.connect(db_url)
        else:
            raise ValueError(f"Unsupported database URL: {db_url}")
            
        self._load_schema_info()
        
    def _load_schema_info(self):
        """Load database schema information."""
        if self.db_type == 'sqlite':
            cursor = self.conn.cursor()
            # Get all tables
            tables = cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table';"
            ).fetchall()
            
            for table in tables:
                table_name = table[0]
                columns = cursor.execute(f"PRAGMA table_info({table_name});").fetchall()
                self.table_columns[table_name] = {col[1]: col for col in columns}
                
        elif self.db_type == 'postgresql':
            cursor = self.conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
            # Get all tables in the public schema
            cursor.execute("""
                SELECT table_name FROM information_schema.tables 
                WHERE table_schema = 'public';
            """)
            tables = cursor.fetchall()
            
            for table in tables:
                table_name = table[0]
                cursor.execute(f"""
                    SELECT column_name, data_type, is_nullable
                    FROM information_schema.columns
                    WHERE table_name = '{table_name}';
                """)
                columns = cursor.fetchall()
                self.table_columns[table_name] = {col[0]: col for col in columns}

    def parse_log_file(self, log_file: str):
        """Parse the application log file to extract SQL queries and execution times."""
        query_pattern = re.compile(r'SQL Query: (.*) - Execution time: (\d+\.\d+)ms')
        
        with open(log_file, 'r') as f:
            for line in f:
                match = query_pattern.search(line)
                if match:
                    query = match.group(1)
                    execution_time = float(match.group(2))
                    
                    # Format the SQL for better analysis
                    formatted_query = sqlparse.format(
                        query, reindent=True, keyword_case='upper'
                    )
                    
                    self.queries.append((formatted_query, execution_time))
                    self.query_frequencies[formatted_query] += 1
                    
                    # Classify slow queries (>100ms)
                    if execution_time > 100:
                        self.slow_queries.append((formatted_query, execution_time))

    def analyze_queries(self):
        """Analyze the collected queries and print statistics."""
        if not self.queries:
            print("No queries found in the log file.")
            return

        total_queries = len(self.queries)
        total_time = sum(time for _, time in self.queries)
        avg_time = total_time / total_queries
        max_time = max(time for _, time in self.queries)
        
        # Get median and percentiles
        times = [time for _, time in self.queries]
        median_time = statistics.median(times)
        p95_time = statistics.quantiles(times, n=20)[18]  # 95th percentile
        
        print(f"\n{'-'*80}")
        print(f"Database Performance Analysis Report")
        print(f"{'-'*80}")
        print(f"Database Type: {self.db_type.upper()}")
        print(f"Total Queries Analyzed: {total_queries}")
        print(f"Total Query Time: {total_time:.2f}ms")
        print(f"Average Query Time: {avg_time:.2f}ms")
        print(f"Median Query Time: {median_time:.2f}ms")
        print(f"95th Percentile Time: {p95_time:.2f}ms")
        print(f"Maximum Query Time: {max_time:.2f}ms")
        print(f"Slow Queries (>100ms): {len(self.slow_queries)}")
        
        # Most frequent queries
        print(f"\n{'-'*80}")
        print(f"Top 5 Most Frequent Queries:")
        print(f"{'-'*80}")
        for query, count in self.query_frequencies.most_common(5):
            print(f"Count: {count}")
            print(f"Query: {query[:100]}...")
            print()
            
        # Slowest queries
        if self.slow_queries:
            print(f"{'-'*80}")
            print(f"Top 5 Slowest Queries:")
            print(f"{'-'*80}")
            
            for query, time in sorted(self.slow_queries, key=lambda x: x[1], reverse=True)[:5]:
                print(f"Time: {time:.2f}ms")
                print(f"Query: {query}")
                print()

    def suggest_indexes(self):
        """Analyze queries and suggest potential indexes for optimization."""
        if not self.queries:
            print("No queries found to suggest indexes.")
            return
            
        # Extract WHERE clauses and JOIN conditions
        where_columns = defaultdict(list)
        join_columns = defaultdict(list)
        order_columns = defaultdict(list)
        
        for query, _ in self.queries:
            # Extract table names
            from_match = re.search(r'FROM\s+([a-zA-Z_][a-zA-Z0-9_]*)', query, re.IGNORECASE)
            if not from_match:
                continue
                
            main_table = from_match.group(1)
            
            # Find WHERE conditions
            where_match = re.search(r'WHERE\s+(.*?)(?:ORDER BY|GROUP BY|LIMIT|$)', query, re.IGNORECASE | re.DOTALL)
            if where_match:
                where_clause = where_match.group(1).strip()
                # Find column comparisons
                col_comparisons = re.findall(r'([a-zA-Z_][a-zA-Z0-9_]*)\s*(?:=|>|<|>=|<=|LIKE)', where_clause)
                for col in col_comparisons:
                    where_columns[main_table].append(col)
            
            # Find JOIN conditions
            join_matches = re.findall(r'JOIN\s+([a-zA-Z_][a-zA-Z0-9_]*)\s+.*?ON\s+(.*?)(?:WHERE|ORDER BY|GROUP BY|LIMIT|JOIN|$)', 
                                      query, re.IGNORECASE | re.DOTALL)
            for join_table, on_clause in join_matches:
                # Find columns in the ON clause
                on_cols = re.findall(r'([a-zA-Z_][a-zA-Z0-9_]*)\.([a-zA-Z_][a-zA-Z0-9_]*)', on_clause)
                for table_name, col_name in on_cols:
                    join_columns[table_name].append(col_name)
            
            # Find ORDER BY columns
            order_match = re.search(r'ORDER BY\s+(.*?)(?:LIMIT|GROUP BY|$)', query, re.IGNORECASE | re.DOTALL)
            if order_match:
                order_clause = order_match.group(1).strip()
                # Find columns in ORDER BY
                order_cols = re.findall(r'([a-zA-Z_][a-zA-Z0-9_]*)', order_clause)
                for col in order_cols:
                    if col.lower() not in ('asc', 'desc'):
                        order_columns[main_table].append(col)
        
        # Suggest indexes based on frequency
        print(f"\n{'-'*80}")
        print(f"Suggested Indexes:")
        print(f"{'-'*80}")
        
        # WHERE clause indexes
        for table, columns in where_columns.items():
            col_counter = Counter(columns)
            for col, count in col_counter.most_common():
                if count >= 3:  # Only suggest for frequently queried columns
                    print(f"CREATE INDEX idx_{table}_{col} ON {table}({col});")
                    print(f"  • Reason: Column appears in WHERE clause {count} times")
                    print()
        
        # JOIN indexes
        for table, columns in join_columns.items():
            col_counter = Counter(columns)
            for col, count in col_counter.most_common():
                if count >= 2:  # Join columns are important
                    print(f"CREATE INDEX idx_{table}_{col} ON {table}({col});")
                    print(f"  • Reason: Column used in JOIN conditions {count} times")
                    print()
                    
        # ORDER BY indexes
        for table, columns in order_columns.items():
            col_counter = Counter(columns)
            for col, count in col_counter.most_common():
                if count >= 3:
                    print(f"CREATE INDEX idx_{table}_{col} ON {table}({col});")
                    print(f"  • Reason: Column used in ORDER BY {count} times")
                    print()
    
    def check_existing_indexes(self):
        """Check which indexes already exist in the database."""
        existing_indexes = {}
        
        if self.db_type == 'sqlite':
            cursor = self.conn.cursor()
            for table_name in self.table_columns.keys():
                indexes = cursor.execute(
                    f"SELECT name, sql FROM sqlite_master WHERE type='index' AND tbl_name='{table_name}';"
                ).fetchall()
                
                if indexes:
                    existing_indexes[table_name] = indexes
                    
        elif self.db_type == 'postgresql':
            cursor = self.conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
            for table_name in self.table_columns.keys():
                cursor.execute(f"""
                    SELECT indexname, indexdef
                    FROM pg_indexes
                    WHERE tablename = '{table_name}';
                """)
                indexes = cursor.fetchall()
                
                if indexes:
                    existing_indexes[table_name] = indexes
        
        if existing_indexes:
            print(f"\n{'-'*80}")
            print(f"Existing Indexes:")
            print(f"{'-'*80}")
            
            for table, indexes in existing_indexes.items():
                print(f"Table: {table}")
                for idx in indexes:
                    print(f"  • {idx[0]}: {idx[1]}")
                print()

    def generate_report(self, output_file: Optional[str] = None):
        """Generate a comprehensive report with all findings."""
        # Convert query data to DataFrame for analysis
        if not self.queries:
            print("No data to generate report.")
            return
            
        df = pd.DataFrame(self.queries, columns=['query', 'execution_time'])
        
        # Create basic statistics
        stats = {
            'total_queries': len(df),
            'total_time': df['execution_time'].sum(),
            'mean_time': df['execution_time'].mean(),
            'median_time': df['execution_time'].median(),
            'p95_time': df['execution_time'].quantile(0.95),
            'max_time': df['execution_time'].max(),
            'slow_queries': len(df[df['execution_time'] > 100])
        }
        
        # Create HTML report
        html = f"""
        <html>
        <head>
            <title>FreelanceFlow Database Performance Report</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                h1, h2, h3 {{ color: #2c3e50; }}
                .container {{ max-width: 1200px; margin: 0 auto; }}
                .stats {{ display: flex; flex-wrap: wrap; gap: 20px; margin-bottom: 30px; }}
                .stat-card {{ background-color: #f8f9fa; border-radius: 8px; padding: 15px; flex: 1; min-width: 200px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
                .stat-value {{ font-size: 24px; font-weight: bold; color: #3498db; margin: 10px 0; }}
                .query-box {{ background-color: #f8f9fa; border-radius: 8px; padding: 15px; margin-bottom: 15px; overflow-x: auto; }}
                .time-value {{ font-weight: bold; color: #e74c3c; }}
                pre {{ margin: 0; white-space: pre-wrap; }}
                .warning {{ color: #e74c3c; }}
                .good {{ color: #2ecc71; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>FreelanceFlow Database Performance Report</h1>
                <p>Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
                <p>Database Type: {self.db_type.upper()}</p>
                
                <h2>Performance Summary</h2>
                <div class="stats">
                    <div class="stat-card">
                        <h3>Total Queries</h3>
                        <div class="stat-value">{stats['total_queries']}</div>
                    </div>
                    <div class="stat-card">
                        <h3>Total Time</h3>
                        <div class="stat-value">{stats['total_time']:.2f}ms</div>
                    </div>
                    <div class="stat-card">
                        <h3>Average Time</h3>
                        <div class="stat-value">{stats['mean_time']:.2f}ms</div>
                    </div>
                    <div class="stat-card">
                        <h3>Median Time</h3>
                        <div class="stat-value">{stats['median_time']:.2f}ms</div>
                    </div>
                    <div class="stat-card">
                        <h3>95th Percentile</h3>
                        <div class="stat-value">{stats['p95_time']:.2f}ms</div>
                    </div>
                    <div class="stat-card">
                        <h3>Slow Queries</h3>
                        <div class="stat-value {('warning' if stats['slow_queries'] > 0 else 'good')}">
                            {stats['slow_queries']}
                        </div>
                    </div>
                </div>
                
                <h2>Slow Queries (>100ms)</h2>
        """
        
        # Add slow queries to the report
        if self.slow_queries:
            for i, (query, time) in enumerate(sorted(self.slow_queries, key=lambda x: x[1], reverse=True)[:10]):
                html += f"""
                <div class="query-box">
                    <p><strong>Query {i+1}</strong> - <span class="time-value">{time:.2f}ms</span></p>
                    <pre>{query}</pre>
                </div>
                """
        else:
            html += "<p>No slow queries detected. Great job!</p>"
            
        # Add most frequent queries
        html += "<h2>Most Frequent Queries</h2>"
        for i, (query, count) in enumerate(self.query_frequencies.most_common(5)):
            html += f"""
            <div class="query-box">
                <p><strong>Query {i+1}</strong> - Executed {count} times</p>
                <pre>{query}</pre>
            </div>
            """
            
        # Close the HTML
        html += """
            </div>
        </body>
        </html>
        """
        
        # Save or display the report
        if output_file:
            with open(output_file, 'w') as f:
                f.write(html)
            print(f"Report saved to {output_file}")
        else:
            # Create output directory if it doesn't exist
            Path('reports').mkdir(exist_ok=True)
            output_path = f"reports/db_performance_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
            with open(output_path, 'w') as f:
                f.write(html)
            print(f"Report saved to {output_path}")


def main():
    """Main function to run the performance analyzer."""
    parser = argparse.ArgumentParser(description='Analyze database performance and suggest optimizations.')
    parser.add_argument('--log-file', required=True, help='Path to the application log file')
    parser.add_argument('--suggest-indexes', action='store_true', help='Suggest indexes based on query patterns')
    parser.add_argument('--check-indexes', action='store_true', help='Check existing indexes in the database')
    parser.add_argument('--report', action='store_true', help='Generate HTML performance report')
    parser.add_argument('--output', help='Output file for the HTML report')
    parser.add_argument('--verbose', action='store_true', help='Show more detailed output')
    args = parser.parse_args()
    
    # Load environment variables
    load_dotenv()
    
    # Get database URL
    db_url = os.environ.get('DATABASE_URL')
    if not db_url:
        print("Error: DATABASE_URL environment variable not found.")
        print("Please set it in your .env file or environment variables.")
        sys.exit(1)
    
    try:
        analyzer = PerformanceAnalyzer(db_url, verbose=args.verbose)
        analyzer.parse_log_file(args.log_file)
        analyzer.analyze_queries()
        
        if args.suggest_indexes:
            analyzer.suggest_indexes()
            
        if args.check_indexes:
            analyzer.check_existing_indexes()
            
        if args.report:
            analyzer.generate_report(args.output)
            
    except Exception as e:
        print(f"Error: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main() 