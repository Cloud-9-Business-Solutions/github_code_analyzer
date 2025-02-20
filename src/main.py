"""
Main entry point for the GitHub Code Analysis Tool.
"""
import argparse
import os
import shutil
from pathlib import Path
import git
from dotenv import load_dotenv, find_dotenv
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from github_handler import GitHubHandler
from code_analyzer import CodeAnalyzer
from report_generator import ReportGenerator

def setup_clone_directory(workspace_root: Path, debug: bool = False) -> Path:
    """
    Set up the clone directory in the workspace root.
    Creates the directory if it doesn't exist, cleans it if it does.
    """
    clone_dir = workspace_root / 'clone'
    
    # Create clone directory if it doesn't exist
    clone_dir.mkdir(exist_ok=True)
    
    # Clean the directory if it exists
    if any(clone_dir.iterdir()):
        if debug:
            print(f"Cleaning existing clone directory: {clone_dir}")
        shutil.rmtree(clone_dir)
        clone_dir.mkdir()
    
    return clone_dir

def parse_args():
    parser = argparse.ArgumentParser(description='Analyze code patterns in GitHub repositories')
    parser.add_argument('--pattern', required=True, help='Pattern to search for in files (e.g., "*.tf", "src/*.py"). Multiple patterns can be specified with commas: "*.tf,*.yaml"')
    parser.add_argument('--contents', help='Search for specific content within matching files. Multiple patterns can be specified with commas: "pattern1,pattern2"')
    parser.add_argument('--org', help='GitHub organization name (overrides GITHUB_ORG env variable)')
    
    # Get output file from environment or use default
    default_output = 'results.csv'  # Default if no environment variable
    
    parser.add_argument(
        '--output',
        default=None,  # Don't set a default here, we'll handle it after loading .env
        help='Output file path (default: value from OUTPUT_FILE env var in reports directory)'
    )
    parser.add_argument('--format', choices=['csv', 'json'], default='csv', help='Output format (default: csv)')
    parser.add_argument('--file-pattern', default='*', help='Glob pattern for files to analyze (default: all files)')
    parser.add_argument('--debug', action='store_true', help='Show debug information')
    parser.add_argument('--keep-clones', action='store_true', help='Keep cloned repositories after analysis')
    
    # Add repository cloning options
    parser.add_argument('--branch', help='Specific branch to analyze (default: repository default branch)')
    parser.add_argument('--limit', type=int, help='Limit the number of repositories to analyze')
    return parser.parse_args()

def main():
    console = Console()
    
    # Parse arguments first to get debug flag
    args = parse_args()
    
    # If pattern looks like a file extension pattern (*.ext), use it as file pattern instead
    if args.pattern.startswith('*.'):
        args.file_pattern = args.pattern
        args.pattern = '.*'  # Match any content in the matching files
        if args.debug:
            console.print(f"\nDetected file extension pattern. Using '{args.file_pattern}' as file pattern and searching for any content.", style="yellow")
    
    github = None
    
    # Load environment variables with detailed feedback
    console.print("\nEnvironment Setup:", style="bold blue")
    
    # Find .env file
    dotenv_path = find_dotenv()
    if not dotenv_path:
        console.print("Error: No .env file found in current or parent directories", style="red")
        return 1
    
    console.print(f"Found .env file at: {dotenv_path}", style="green")
    
    # Clear any existing environment variables
    if 'GH_ORG' in os.environ:
        del os.environ['GH_ORG']
    
    # Load environment variables
    load_dotenv(dotenv_path, override=True)
    
    # Set output path after loading environment variables
    if args.output is None:
        # Use OUTPUT_FILE from environment, or default to results.csv
        output_file = os.getenv('OUTPUT_FILE', 'results.csv')
        if not os.path.isabs(output_file):
            # If relative path and doesn't start with 'reports/', put it in reports directory
            if not output_file.startswith('reports/'):
                args.output = str(Path('reports') / output_file)
            else:
                args.output = output_file
        else:
            args.output = output_file
        
        if args.debug:
            console.print(f"Using output file from environment: {args.output}", style="blue")
    
    # Verify environment variables
    github_token = os.getenv('GH_TOKEN')
    github_org = os.getenv('GH_ORG')
    
    if args.debug:
        console.print("\nDebug Information:", style="yellow")
        console.print(f"GH_ORG value: {github_org}")
        console.print(f"Token starts with: {github_token[:10]}..." if github_token else "No token found")
        console.print(f"Working directory: {os.getcwd()}")
        console.print(f".env file path: {dotenv_path}")
    
    if not github_token or not github_org:
        console.print("\nError: Required environment variables not found in .env file", style="red")
        console.print("Please ensure GH_TOKEN and GH_ORG are set", style="red")
        return 1
    
    try:
        # Show current configuration
        console.print("\nConfiguration:", style="bold blue")
        effective_org = args.org or github_org
        console.print(f"Organization: {effective_org}")
        console.print(f"Pattern: {args.pattern}")
        console.print(f"File pattern: {args.file_pattern}")
        if args.limit:
            console.print(f"Repository limit: {args.limit}")
        console.print()
        
        # Initialize components
        github = GitHubHandler(debug=args.debug)
        report_gen = ReportGenerator()
        
        # Get repositories
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Fetching repositories...", total=None)
            repos = github.list_repositories(args.org)
            progress.update(task, completed=True)
        
        # Apply repository limit if specified
        if args.limit and args.limit > 0:
            repos = repos[:args.limit]
            console.print(f"Limiting analysis to {args.limit} repositories", style="blue")
        
        console.print(f"Found {len(repos)} repositories", style="green")
        if not repos:
            console.print("No repositories found to analyze", style="yellow")
            return 0
        
        # Set up clone directory
        workspace_root = Path(os.getcwd())
        clone_dir = setup_clone_directory(workspace_root, args.debug)
        if args.debug:
            console.print(f"\nUsing clone directory: {clone_dir}", style="blue")
        
        # Process each repository
        all_results = {}
        try:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                for repo in repos:
                    task = progress.add_task(f"Analyzing {repo.full_name}...", total=None)
                    try:
                        repo_path = clone_dir / repo.name
                        
                        # Clone the repository with shallow clone
                        if args.debug:
                            console.print(f"\nCloning {repo.full_name}...", style="blue")
                        
                        github.clone_repository(
                            repo,
                            repo_path,
                            branch=args.branch
                        )
                        
                        if args.debug:
                            console.print(f"Analyzing repository structure...", style="blue")
                        
                        # Analyze files
                        analyzer = CodeAnalyzer(str(repo_path), args.file_pattern, debug=args.debug)
                        files = analyzer.find_files()
                        if files:
                            if args.debug:
                                console.print(f"\nFound {len(files)} files to analyze in {repo.name}:", style="blue")
                                for f in files:
                                    console.print(f"  - {f}", style="dim")
                            
                            # Handle multiple patterns
                            patterns = [p.strip() for p in args.pattern.split(',')]
                            content_patterns = [p.strip() for p in args.contents.split(',')] if args.contents else None
                            
                            if args.debug:
                                console.print(f"\nSearching for patterns: {patterns}", style="blue")
                                if content_patterns:
                                    console.print(f"Content patterns: {content_patterns}", style="blue")
                            
                            results = {}
                            if args.contents:
                                # When searching for content, use the files we already found
                                for content in content_patterns:
                                    pattern_results = analyzer.search_pattern(files, content)
                                    if pattern_results:
                                        results.update(pattern_results)
                            else:
                                # When searching for file patterns only
                                for pattern in patterns:
                                    pattern_results = analyzer.search_pattern(files, pattern)
                                    if pattern_results:
                                        results.update(pattern_results)
                            
                            if results:
                                all_results.update(results)
                        else:
                            if args.debug:
                                console.print(f"No matching files found in {repo.name}", style="yellow")
                        
                        progress.update(task, completed=True)
                    except git.GitCommandError as e:
                        console.print(f"Error cloning {repo.full_name}: {str(e)}", style="red")
                        progress.update(task, completed=True)
                        continue
                    except Exception as e:
                        console.print(f"Error processing {repo.full_name}: {str(e)}", style="red")
                        progress.update(task, completed=True)
                        continue
        finally:
            # Clean up clone directory unless --keep-clones is specified
            if not args.keep_clones and clone_dir.exists():
                if args.debug:
                    console.print("\nCleaning up clone directory...", style="blue")
                shutil.rmtree(clone_dir)
                clone_dir.mkdir()  # Recreate empty directory
        
        # Generate report
        if all_results:
            try:
                # Ensure output directory exists
                output_path = Path(args.output).resolve()
                output_path.parent.mkdir(parents=True, exist_ok=True)
                
                if args.debug:
                    console.print(f"\nSaving results to: {output_path}", style="blue")
                    console.print(f"Number of results to save: {len(all_results)}", style="blue")
                
                # Save the results
                try:
                    if args.format == 'json':
                        report_gen.export_json(all_results, str(output_path))
                    else:
                        report_gen.export_csv(all_results, str(output_path))
                except Exception as save_error:
                    console.print(f"\nError during file save operation: {str(save_error)}", style="red")
                    raise save_error
                
                # Print summary before checking file
                report_gen.print_summary(all_results)
                
                # Verify the file was saved
                if output_path.exists():
                    try:
                        # Check file size
                        file_size = output_path.stat().st_size
                        if file_size > 0:
                            console.print(f"\nResults saved successfully to {output_path} ({file_size} bytes)", style="green")
                        else:
                            console.print(f"\nWarning: File was created but is empty: {output_path}", style="yellow")
                    except Exception as stat_error:
                        console.print(f"\nWarning: Could not verify file size: {str(stat_error)}", style="yellow")
                else:
                    console.print(f"\nError: Failed to save results to {output_path}", style="red")
                    raise FileNotFoundError(f"Output file was not created: {output_path}")
            except Exception as e:
                console.print(f"\nError saving results: {str(e)}", style="red")
                if args.debug:
                    console.print("\nDebug information:", style="yellow")
                    console.print(f"Output path: {output_path}", style="yellow")
                    console.print(f"Output directory exists: {output_path.parent.exists()}", style="yellow")
                    console.print(f"Output directory is writable: {os.access(output_path.parent, os.W_OK)}", style="yellow")
                raise
        else:
            console.print("\nNo matches found", style="yellow")
    
    except Exception as e:
        console.print(f"\nError: {str(e)}", style="red")
        return 1
    finally:
        if github:
            github.close()
    
    return 0

if __name__ == '__main__':
    exit(main()) 