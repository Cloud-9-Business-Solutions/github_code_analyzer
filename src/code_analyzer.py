"""
Code analysis module for pattern matching in files.
"""
from typing import List, Dict, Pattern, Optional, Set
import re
from pathlib import Path
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from rich.progress import Progress, SpinnerColumn, TextColumn
from fnmatch import fnmatch

@dataclass
class SearchMatch:
    """Represents a pattern match in a file."""
    line_number: int
    line_content: str
    match_text: str
    context_before: List[str]
    context_after: List[str]

class CodeAnalyzer:
    def __init__(self, base_path: str, file_pattern: str = "*", debug: bool = False):
        """
        Initialize code analyzer with base path for scanning.
        
        Args:
            base_path: Base directory path to scan
            file_pattern: Glob pattern for files to analyze (default: all files)
            debug: Enable debug logging
        """
        self.base_path = Path(base_path)
        self.file_pattern = file_pattern
        self.debug = debug
        
        # Configure logging
        self.logger = logging.getLogger(__name__)
        if debug:
            self.logger.setLevel(logging.DEBUG)
            # Add console handler if none exists
            if not self.logger.handlers:
                handler = logging.StreamHandler()
                handler.setFormatter(logging.Formatter('%(levelname)s: %(message)s'))
                self.logger.addHandler(handler)
    
    def is_binary_file(self, file_path: Path) -> bool:
        """Check if a file is binary by reading its first few bytes."""
        try:
            with open(file_path, 'rb') as f:
                chunk = f.read(1024)
                return b'\0' in chunk
        except Exception:
            return True
    
    def should_skip_path(self, path: Path) -> bool:
        """Check if a path should be skipped."""
        # Skip .git directories and their contents
        if '.git' in path.parts or str(path).startswith('.git'):
            if self.debug:
                self.logger.debug(f"Skipping git path: {path}")
            return True
        
        # Skip hidden files and directories
        if any(part.startswith('.') for part in path.parts):
            if self.debug:
                self.logger.debug(f"Skipping hidden path: {path}")
            return True
        
        # Skip common binary file extensions
        binary_extensions = {'.pyc', '.so', '.pyd', '.dll', '.exe', '.bin', '.pkl', '.pdb'}
        if path.suffix.lower() in binary_extensions:
            if self.debug:
                self.logger.debug(f"Skipping binary file: {path}")
            return True
            
        # Handle file patterns
        patterns = self.file_pattern.split(',') if ',' in self.file_pattern else [self.file_pattern]
        patterns = [p.strip().replace('\n', '') for p in patterns]  # Remove any newlines and whitespace
        
        # Check if file matches any of the patterns
        for pattern in patterns:
            if fnmatch(path.name, pattern):
                if self.debug:
                    self.logger.debug(f"File matches pattern {pattern}: {path}")
                return False  # Don't skip if it matches any pattern
        
        if self.debug:
            self.logger.debug(f"File does not match any patterns: {path}")
        return True  # Skip if it doesn't match any pattern
    
    def find_files(self) -> List[Path]:
        """Find all matching files in the base path."""
        matching_files = []
        seen_files = set()  # To avoid duplicates
        
        if self.debug:
            self.logger.debug(f"Searching in directory: {self.base_path}")
            self.logger.debug(f"Using file patterns: {self.file_pattern}")
        
        try:
            # Get file patterns
            patterns = self.file_pattern.split(',') if ',' in self.file_pattern else [self.file_pattern]
            patterns = [p.strip().replace('\n', '') for p in patterns]  # Remove any newlines and whitespace
            
            if self.debug:
                self.logger.debug(f"Expanded patterns: {patterns}")
            
            # Use glob patterns that exclude .git directories
            for pattern in patterns:
                if '/' in pattern:
                    # For directory-specific patterns, use them directly
                    for file_path in self.base_path.glob(pattern):
                        if self._should_process_file(file_path, seen_files):
                            if self.debug:
                                self.logger.debug(f"Found file matching directory pattern '{pattern}': {file_path}")
                            matching_files.append(file_path)
                            seen_files.add(str(file_path))
                else:
                    # For general patterns, search in root and subdirectories
                    # Search in root directory
                    for file_path in self.base_path.glob(pattern):
                        if self._should_process_file(file_path, seen_files):
                            matching_files.append(file_path)
                            seen_files.add(str(file_path))
                    
                    # Search recursively in subdirectories (excluding .git and hidden dirs)
                    for file_path in self.base_path.glob(f"**/[!.]*/{pattern}"):
                        if self._should_process_file(file_path, seen_files):
                            matching_files.append(file_path)
                            seen_files.add(str(file_path))
            
            if self.debug:
                self.logger.debug(f"Total files to search: {len(matching_files)}")
                if matching_files:
                    self.logger.debug("Files to search:")
                    for f in matching_files:
                        self.logger.debug(f"  {f.relative_to(self.base_path)}")
            
            return matching_files
            
        except Exception as e:
            self.logger.error(f"Error finding files: {str(e)}")
            return []
    
    def _should_process_file(self, file_path: Path, seen_files: Set[str]) -> bool:
        """Helper method to determine if a file should be processed."""
        # Skip if not a file
        if not file_path.is_file():
            return False
        
        # Skip if we've seen this file before
        file_str = str(file_path)
        if file_str in seen_files:
            return False
        
        # Skip if in .git directory
        if '.git' in file_path.parts:
            return False
        
        # Skip if hidden file/directory
        if any(part.startswith('.') for part in file_path.parts):
            return False
        
        # Skip binary files
        if self.is_binary_file(file_path):
            if self.debug:
                self.logger.debug(f"Skipping binary file: {file_path}")
            return False
        
        if self.debug:
            self.logger.debug(f"Adding file to search list: {file_path}")
        return True
    
    def get_context_lines(self, lines: List[str], current_idx: int, context_size: int = 2) -> tuple[List[str], List[str]]:
        """Get context lines before and after a match."""
        start_idx = max(0, current_idx - context_size)
        end_idx = min(len(lines), current_idx + context_size + 1)
        
        before = [line.strip() for line in lines[start_idx:current_idx]]
        after = [line.strip() for line in lines[current_idx + 1:end_idx]]
        
        return before, after
    
    def process_file(self, file_path: Path, pattern: str, context_size: int = 2) -> Optional[Dict]:
        """Process a single file for pattern matching."""
        try:
            if not file_path.exists():
                if self.debug:
                    self.logger.debug(f"File does not exist: {file_path}")
                return None
                
            if not file_path.is_file():
                if self.debug:
                    self.logger.debug(f"Path is not a file: {file_path}")
                return None
                
            if self.debug:
                self.logger.debug(f"Processing file: {file_path}")
                self.logger.debug(f"Using search pattern: '{pattern}'")
            
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    lines = content.splitlines()
            except UnicodeDecodeError:
                if self.debug:
                    self.logger.debug(f"Skipping binary file: {file_path}")
                return None
            except Exception as e:
                self.logger.error(f"Error reading file {file_path}: {str(e)}")
                return None
                
            if self.debug:
                self.logger.debug(f"File {file_path} has {len(lines)} lines")
                # Show first few lines of content for debugging
                preview_lines = min(5, len(lines))
                if preview_lines > 0:
                    self.logger.debug(f"First {preview_lines} lines of content:")
                    for i, line in enumerate(lines[:preview_lines], 1):
                        self.logger.debug(f"  {i}: {line.strip()}")
            
            matches = []
            try:
                # Convert glob pattern to regex pattern if it contains glob characters
                if any(c in pattern for c in '*?[]'):
                    # Escape special regex characters except * and ?
                    escaped_pattern = re.escape(pattern).replace('\\*', '.*').replace('\\?', '.')
                    if self.debug:
                        self.logger.debug(f"Converted glob pattern '{pattern}' to regex pattern '{escaped_pattern}'")
                    pattern = escaped_pattern
                
                compiled_pattern = re.compile(pattern, re.IGNORECASE)  # Make pattern matching case-insensitive
            except re.error as e:
                self.logger.error(f"Invalid regular expression pattern '{pattern}': {str(e)}")
                return None
            
            if self.debug:
                self.logger.debug(f"Searching with compiled pattern: {compiled_pattern.pattern}")
            
            # Search for pattern matches with more context
            for line_num, line in enumerate(lines, 1):
                try:
                    if compiled_pattern.search(line):
                        if self.debug:
                            self.logger.debug(f"Found match in {file_path} at line {line_num}: {line.strip()}")
                            self.logger.debug(f"Match found using pattern: '{pattern}'")
                        
                        before, after = self.get_context_lines(lines, line_num - 1, context_size)
                        match = SearchMatch(
                            line_number=line_num,
                            line_content=line.strip(),
                            match_text=line.strip(),
                            context_before=before,
                            context_after=after
                        )
                        matches.append(vars(match))
                except Exception as e:
                    self.logger.error(f"Error processing line {line_num} in {file_path}: {str(e)}")
                    continue
            
            if matches:
                return {
                    'file_path': str(file_path),
                    'matches': matches
                }
            
            if self.debug:
                self.logger.debug(f"No matches found in {file_path} for pattern: '{pattern}'")
            
        except Exception as e:
            self.logger.error(f"Error processing file {file_path}: {str(e)}")
        
        return None
    
    def search_pattern(self, files: List[Path], pattern: str, max_workers: int = 4) -> Dict[str, List[Dict]]:
        """
        Search for pattern in files using parallel processing.
        
        Args:
            files: List of files to search
            pattern: Regular expression pattern to search for
            max_workers: Maximum number of parallel workers
            
        Returns:
            Dictionary mapping file paths to lists of matches
        """
        results = {}
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_file = {
                executor.submit(self.process_file, file_path, pattern): file_path 
                for file_path in files
            }
            
            for future in as_completed(future_to_file):
                result = future.result()
                if result:
                    results[result['file_path']] = {
                        'matches': result['matches']
                    }
        
        return results 