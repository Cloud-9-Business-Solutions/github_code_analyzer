"""
GitHub integration module for repository operations.
"""
from typing import List, Optional, Union
import os
from pathlib import Path
import git
from github import Github, GithubException
from github.Repository import Repository
from github.Organization import Organization
from rich.progress import Progress
from rich.console import Console

class GitHubHandler:
    def __init__(self, token: Optional[str] = None, debug: bool = False):
        """Initialize GitHub handler with authentication token."""
        self.console = Console()
        self.debug = debug
        
        # Get token with debug info
        self.token = token or os.getenv('GITHUB_TOKEN')
        if self.debug:
            self.console.print("\nGitHub Handler Debug:", style="yellow")
            self.console.print(f"Token environment variable present: {'GITHUB_TOKEN' in os.environ}")
            if self.token:
                self.console.print(f"Token starts with: {self.token[:10]}...")
                self.console.print(f"Token length: {len(self.token)}")
                # Test token with curl-like request
                import requests
                headers = {'Authorization': f'token {self.token}'}
                response = requests.get('https://api.github.com/user', headers=headers)
                self.console.print(f"Direct API test status code: {response.status_code}")
                if response.status_code == 200:
                    self.console.print(f"API test successful, authenticated as: {response.json().get('login')}")
                else:
                    self.console.print(f"API test failed: {response.json()}", style="red")
        
        if not self.token:
            raise ValueError("GitHub token is required. Set GITHUB_TOKEN environment variable or pass token directly.")
        
        # Validate token format
        if not self.token.startswith(('ghp_', 'github_pat_')):
            raise ValueError("Invalid GitHub token format. Token should start with 'ghp_' or 'github_pat_'")
        
        # Initialize GitHub client
        self.github = Github(self.token)
        
        # Verify authentication
        try:
            # Test API access by getting the authenticated user
            user = self.github.get_user()
            rate_limit = self.github.get_rate_limit()
            self.console.print(f"Authenticated as {user.login}", style="green")
            self.console.print(f"Rate limit: {rate_limit.core.remaining}/{rate_limit.core.limit}", style="blue")
        except GithubException as e:
            if e.status == 401:
                if self.debug:
                    self.console.print("\nAuthentication Debug:", style="red")
                    self.console.print(f"Full error response: {e.data}")
                raise ValueError(
                    "GitHub authentication failed. Please check your token is valid and has the required permissions:\n"
                    "- repo (Full control of private repositories)\n"
                    "- read:org (Read organization membership)\n"
                    f"\nError details: {e.data.get('message', str(e))}"
                ) from e
            raise
    
    def get_organization(self, org_name: Optional[str] = None) -> Organization:
        """Get GitHub organization."""
        org_name = org_name or os.getenv('GITHUB_ORG')
        if self.debug:
            self.console.print(f"\nTrying to access organization: {org_name}", style="yellow")
        
        if not org_name:
            raise ValueError("Organization name is required. Set GITHUB_ORG environment variable or pass org_name directly.")
        
        try:
            return self.github.get_organization(org_name)
        except GithubException as e:
            if e.status == 404:
                raise ValueError(f"Organization '{org_name}' not found or you don't have access to it.") from e
            raise
    
    def _load_excluded_repos(self, exclusion_file: str = None) -> set:
        """Load repository names to exclude from the analysis."""
        excluded_repos = set()
        try:
            # Get exclusion file path from environment variable or use default
            exclusion_file = exclusion_file or os.getenv('EXCLUSIONS_FILE', 'exclusions/repos.csv')
            
            if Path(exclusion_file).exists():
                if self.debug:
                    self.console.print(f"\nLoading exclusions from: {exclusion_file}", style="yellow")
                with open(exclusion_file, 'r') as f:
                    # Skip header if it exists
                    first_line = f.readline().strip()
                    if not first_line.lower() == 'repository':
                        excluded_repos.add(first_line)
                    # Read remaining lines
                    for line in f:
                        repo = line.strip()
                        if repo:  # Skip empty lines
                            excluded_repos.add(repo)
                if self.debug:
                    self.console.print(f"Excluded repositories: {', '.join(sorted(excluded_repos))}", style="yellow")
            elif self.debug:
                self.console.print(f"Exclusions file not found at: {exclusion_file}", style="yellow")
        except Exception as e:
            self.console.print(f"Warning: Error loading exclusions file: {str(e)}", style="yellow")
        return excluded_repos

    def _load_included_repos(self, inclusion_file: str = None) -> set:
        """Load repository names to include in the analysis."""
        included_repos = set()
        try:
            # Get inclusion file path from environment variable or use default
            inclusion_file = inclusion_file or os.getenv('INCLUSIONS_FILE', 'inclusions/repos.csv')
            
            if Path(inclusion_file).exists():
                if self.debug:
                    self.console.print(f"\nLoading inclusions from: {inclusion_file}", style="yellow")
                with open(inclusion_file, 'r') as f:
                    # Skip header if it exists
                    first_line = f.readline().strip()
                    if not first_line.lower() == 'repository':
                        included_repos.add(first_line)
                    # Read remaining lines
                    for line in f:
                        repo = line.strip()
                        if repo:  # Skip empty lines
                            included_repos.add(repo)
                if self.debug:
                    self.console.print(f"Included repositories: {', '.join(sorted(included_repos))}", style="yellow")
            elif self.debug:
                self.console.print(f"Inclusions file not found at: {inclusion_file}", style="yellow")
        except Exception as e:
            self.console.print(f"Warning: Error loading inclusions file: {str(e)}", style="yellow")
        return included_repos

    def list_repositories(self, org_name: Optional[str] = None) -> List[Repository]:
        """List repositories in the organization, applying inclusion and exclusion filters."""
        org = self.get_organization(org_name)
        try:
            # Load included and excluded repositories
            included_repos = self._load_included_repos()
            excluded_repos = self._load_excluded_repos()
            
            # Get all repositories
            repos = org.get_repos()
            
            # Filter repositories based on inclusion/exclusion rules
            filtered_repos = []
            for repo in repos:
                # Skip if explicitly excluded
                if repo.name in excluded_repos:
                    if self.debug:
                        self.console.print(f"Skipping excluded repository: {repo.name}", style="yellow")
                    continue
                
                # If inclusion list exists, only include repos from that list
                if included_repos and repo.name not in included_repos:
                    if self.debug:
                        self.console.print(f"Skipping repository not in inclusion list: {repo.name}", style="yellow")
                    continue
                
                filtered_repos.append(repo)
            
            if self.debug:
                self.console.print(f"\nFound {len(filtered_repos)} repositories in {org.login} (after filtering)", style="yellow")
                if excluded_repos:
                    self.console.print(f"Skipped {len(excluded_repos)} excluded repositories", style="yellow")
                if included_repos:
                    self.console.print(f"Filtered to {len(included_repos)} included repositories", style="yellow")
            return filtered_repos
        except GithubException as e:
            if e.status == 403:
                raise ValueError(
                    f"Access denied to organization '{org_name}'. "
                    "Please check your token has the required permissions."
                ) from e
            raise
    
    def clone_repository(
        self,
        repo: Repository,
        target_path: Path,
        branch: Optional[str] = None,
    ) -> Path:
        """
        Clone a repository to the target path using shallow clone (depth=1).
        
        Args:
            repo: GitHub repository object
            target_path: Path where to clone the repository
            branch: Specific branch to clone (None for default branch)
            
        Returns:
            Path to the cloned repository
        
        Raises:
            git.GitCommandError: If cloning fails
            ValueError: If target path already exists
        """
        if target_path.exists():
            raise ValueError(f"Target path already exists: {target_path}")
        
        # Construct clone URL with authentication
        clone_url = repo.clone_url.replace('https://', f'https://{self.token}@')
        
        try:
            if self.debug:
                self.console.print(f"\nCloning {repo.full_name}:", style="blue")
                self.console.print(f"Target path: {target_path}", style="dim")
                self.console.print(f"Branch: {branch or 'default'}", style="dim")
            
            # Prepare clone options with shallow clone (depth=1)
            clone_opts = {
                'url': clone_url,
                'to_path': str(target_path),
                'depth': 1,  # Always use shallow clone
                'progress': None,  # Disable progress output
            }
            
            # Add branch if specified
            if branch:
                clone_opts['branch'] = branch
                clone_opts['single_branch'] = True
            
            # Clone the repository
            repo = git.Repo.clone_from(**clone_opts)
            
            if self.debug:
                # Count total files (excluding .git)
                files = list(target_path.rglob('*'))
                file_count = sum(1 for f in files if f.is_file() and '.git' not in str(f))
                self.console.print(f"Cloned {file_count} files", style="green")
            
            return target_path
            
        except git.GitCommandError as e:
            if target_path.exists():
                import shutil
                shutil.rmtree(target_path, ignore_errors=True)
            raise git.GitCommandError(f"Failed to clone repository {repo.full_name}", e.status)
    
    def close(self):
        """Close GitHub connection."""
        self.github.close() 