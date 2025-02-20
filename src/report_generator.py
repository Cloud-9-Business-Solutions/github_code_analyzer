"""
Report generation module for code analysis results.
"""
from typing import Dict, List, Tuple
import json
import csv
from pathlib import Path
import pandas as pd
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.syntax import Syntax
import os

class ReportGenerator:
    def __init__(self):
        """Initialize report generator."""
        self.console = Console()
    
    def _get_relative_path(self, full_path: str) -> Tuple[str, str]:
        """Extract repository name and relative path from full path."""
        try:
            parts = Path(full_path).parts
            try:
                # Find the 'clone' directory index
                clone_idx = parts.index('clone')
                if len(parts) > clone_idx + 1:
                    repo_name = parts[clone_idx + 1]
                    # Get the path after the repository name
                    relative_parts = parts[clone_idx + 2:]
                    relative_path = str(Path(*relative_parts))
                    return repo_name, relative_path
            except ValueError:
                # If 'clone' not found in path, try to get a reasonable path
                if len(parts) > 0:
                    return parts[-2] if len(parts) > 1 else "", parts[-1]
        except Exception as e:
            self.console.print(f"Error processing path '{full_path}': {str(e)}", style="red")
        return "", str(full_path)
    
    def _get_repo_url(self, repo_name: str) -> str:
        """Generate GitHub repository URL."""
        if repo_name:
            org = os.getenv('GH_ORG', '')
            if org:
                return f"https://github.com/{org}/{repo_name}"
        return ""
    
    def export_json(self, data: Dict, output_path: str):
        """Export results to JSON file."""
        try:
            processed_data = {}
            for file_path, file_data in data.items():
                try:
                    repo_name, relative_path = self._get_relative_path(file_path)
                    if repo_name not in processed_data:
                        processed_data[repo_name] = {
                            'url': self._get_repo_url(repo_name),
                            'files': {}
                        }
                    processed_data[repo_name]['files'][relative_path] = file_data
                except Exception as e:
                    self.console.print(f"Error processing file '{file_path}': {str(e)}", style="red")
            
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(processed_data, f, indent=2)
        except Exception as e:
            self.console.print(f"Error exporting to JSON: {str(e)}", style="red")
            raise
    
    def export_csv(self, data: Dict, output_path: str):
        """Export results to CSV file with repository name, URL, file path, and line number."""
        try:
            # Create a list to store all entries (including multiple matches per file)
            all_entries = []
            
            # Process all files
            for file_path, file_data in data.items():
                try:
                    repo_name, relative_path = self._get_relative_path(file_path)
                    if repo_name and relative_path:  # Only add if we have both
                        repo_url = self._get_repo_url(repo_name)
                        
                        # Get matches from file data
                        matches = file_data.get('matches', [])
                        if matches:
                            # Add an entry for each match with its line number
                            for match in matches:
                                all_entries.append({
                                    'repository': repo_name,
                                    'repository_url': repo_url,
                                    'file_path': relative_path,
                                    'line_number': match.get('line_number', '')
                                })
                        else:
                            # If no matches (file-only results), add entry without line number
                            all_entries.append({
                                'repository': repo_name,
                                'repository_url': repo_url,
                                'file_path': relative_path,
                                'line_number': ''
                            })
                except Exception as e:
                    self.console.print(f"Error processing file '{file_path}': {str(e)}", style="red")
            
            if all_entries:
                try:
                    # Create DataFrame
                    df = pd.DataFrame(all_entries)
                    
                    # Ensure the output directory exists
                    output_path = Path(output_path)
                    output_path.parent.mkdir(parents=True, exist_ok=True)
                    
                    # Save to CSV with explicit encoding
                    df.to_csv(output_path, index=False, encoding='utf-8')
                    
                    # Verify the file was saved
                    if not output_path.exists():
                        raise FileNotFoundError(f"Failed to create output file: {output_path}")
                    
                    # Check file size
                    file_size = output_path.stat().st_size
                    if file_size == 0:
                        raise ValueError(f"Output file was created but is empty: {output_path}")
                    
                    self.console.print(f"Successfully exported {len(all_entries)} entries to CSV", style="green")
                except Exception as e:
                    self.console.print(f"Error writing CSV file: {str(e)}", style="red")
                    raise
            else:
                self.console.print("Warning: No data to export to CSV", style="yellow")
                # Create an empty file to indicate processing completed
                Path(output_path).touch()
        except Exception as e:
            self.console.print(f"Error exporting to CSV: {str(e)}", style="red")
            raise
    
    def print_summary(self, data: Dict):
        """Print summary of results to console."""
        try:
            # Pattern matches table
            matches_table = Table(title="Files Found")
            matches_table.add_column("Repository", style="blue")
            matches_table.add_column("File", style="cyan")
            matches_table.add_column("Content", style="green")
            
            # Track unique repositories and their files
            repo_files = {}
            
            for file_path, file_data in data.items():
                try:
                    repo_name, relative_path = self._get_relative_path(file_path)
                    
                    # Get the first match content if available
                    matches = file_data.get('matches', [])
                    content = ""
                    if matches:
                        first_match = matches[0]
                        content = first_match.get('line_content', '').strip()
                        if len(matches) > 1:
                            content += f"\n... and {len(matches) - 1} more matches"
                    
                    matches_table.add_row(
                        repo_name or "Unknown",
                        relative_path,
                        content
                    )
                    
                    # Track files by repository
                    if repo_name not in repo_files:
                        repo_files[repo_name] = set()
                    repo_files[repo_name].add(relative_path)
                    
                except Exception as e:
                    self.console.print(f"Error processing file '{file_path}': {str(e)}", style="red")
            
            if repo_files:
                self.console.print(matches_table)
                
                # Print repository summary
                if len(repo_files) > 1:
                    repo_table = Table(title="\nFiles by Repository")
                    repo_table.add_column("Repository", style="blue")
                    repo_table.add_column("Files Found", style="cyan")
                    repo_table.add_column("Total Matches", style="green")
                    
                    for repo, files in sorted(repo_files.items()):
                        # Count total matches for this repository
                        total_matches = sum(
                            len(data[str(Path('clone') / repo / file)].get('matches', []))
                            for file in files
                        )
                        repo_table.add_row(
                            repo or "Unknown",
                            str(len(files)),
                            str(total_matches)
                        )
                    
                    self.console.print(repo_table)
                
                # Print total
                total_files = sum(len(files) for files in repo_files.values())
                total_matches = sum(
                    len(file_data.get('matches', []))
                    for file_data in data.values()
                )
                self.console.print(f"\nTotal files found: {total_files}", style="bold cyan")
                self.console.print(f"Total matches found: {total_matches}", style="bold green")
                
                # Show hint for detailed matches
                if total_matches > 0:
                    self.print_detailed_matches(data)
            else:
                self.console.print("No files found", style="yellow")
        except Exception as e:
            self.console.print(f"Error generating summary: {str(e)}", style="red")
    
    def print_detailed_matches(self, data: Dict, max_matches: int = 5):
        """Print detailed match information with context."""
        try:
            # Group matches by repository
            repo_matches = {}
            for file_path, file_data in data.items():
                try:
                    repo_name, relative_path = self._get_relative_path(file_path)
                    if repo_name not in repo_matches:
                        repo_matches[repo_name] = {}
                    repo_matches[repo_name][relative_path] = file_data.get('matches', [])
                except Exception as e:
                    self.console.print(f"Error processing file '{file_path}': {str(e)}", style="red")
            
            # Print matches by repository
            for repo_name, files in repo_matches.items():
                if any(matches for matches in files.values()):
                    self.console.print(f"\nRepository: {repo_name or 'Unknown'}", style="bold blue")
                    
                    for file_path, matches in files.items():
                        if matches:  # Only show files with matches
                            self.console.print(f"\nFile: {file_path}", style="bold cyan")
                            
                            for i, match in enumerate(matches[:max_matches], 1):
                                try:
                                    # Create panel content with context
                                    content_lines = []
                                    
                                    # Add context before
                                    if match.get('context_before'):
                                        content_lines.extend(match.get('context_before', []))
                                    
                                    # Add the matching line with syntax highlighting
                                    line_content = match.get('line_content', '').rstrip()
                                    content_lines.append(f"[yellow]{line_content}[/yellow]")
                                    
                                    # Add context after
                                    if match.get('context_after'):
                                        content_lines.extend(match.get('context_after', []))
                                    
                                    self.console.print(
                                        Panel(
                                            "\n".join(content_lines),
                                            title=f"Match {i} (Line {match.get('line_number', '?')})",
                                            border_style="magenta"
                                        )
                                    )
                                except Exception as e:
                                    self.console.print(f"Error displaying match: {str(e)}", style="red")
                            
                            if len(matches) > max_matches:
                                self.console.print(
                                    f"... and {len(matches) - max_matches} more matches",
                                    style="dim"
                                )
        except Exception as e:
            self.console.print(f"Error displaying detailed matches: {str(e)}", style="red") 