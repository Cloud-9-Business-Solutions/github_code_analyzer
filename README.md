# GitHub Code Analysis Tool

A Python tool for analyzing code patterns across multiple repositories within a GitHub organization. This tool helps identify specific patterns in code, making it easier to audit and maintain code at scale.

## Features

- GitHub organization repository scanning
- Multiple pattern matching support
- Flexible pattern matching for files
- Content search within matching files
- Repository inclusion and exclusion support
- CSV and JSON report generation
- Rich console output with progress indicators
- Temporary local cloning for efficient analysis
- Repository limit control for targeted analysis

## Prerequisites

- Python 3.8 or higher
- GitHub Personal Access Token with appropriate permissions
- Access to target GitHub organization

## Installation

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd <repository-directory>
   ```

2. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # Unix/macOS
   # or
   .\venv\Scripts\activate  # Windows
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Configure environment variables:
   ```bash
   cp .env.example .env
   ```
   Edit `.env` file and add your GitHub token and organization name:
   ```
   GITHUB_TOKEN=your_token_here
   GITHUB_ORG=your_organization_name
   ```

## Usage

### Basic File Pattern Search
Find files matching a specific pattern:
```bash
# Find all Terraform files
python src/main.py --pattern "*.tf"

# Find all Python files
python src/main.py --pattern "*.py"

# Find files in specific directories
python src/main.py --pattern "src/*.js"
```

### Content Search
Search for specific content within matching files:
```bash
# Find Terraform files containing specific version
python src/main.py --pattern "*.tf" --contents "required_version = \"~> 1.5.0\""

# Find TODO comments in Python files
python src/main.py --pattern "*.py" --contents "TODO:"

# Search for security-related patterns
python src/main.py --pattern "*.yaml" --contents "apiKey:"
```

### Output Options
Control how results are saved:
```bash
# Export as CSV (default)
python src/main.py --pattern "*.tf" --output "reports/results.csv"

# Export as JSON
python src/main.py --pattern "*.tf" --format json --output "reports/results.json"
```

### Repository Filtering
You can control which repositories to analyze using both inclusion and exclusion lists:

#### Repository Inclusions
To analyze only specific repositories, list them in `inclusions/repos.csv`:

1. Create or edit `inclusions/repos.csv`
2. Add one repository name per line
3. The first line can optionally be a header "repository"

Example `inclusions/repos.csv`:
```csv
repository
main-app
api-service
frontend-web
```

Only repositories listed in the inclusions file will be analyzed. If the inclusions file is empty or doesn't exist, all repositories will be considered (subject to exclusions).

#### Repository Exclusions
You can exclude specific repositories from the analysis by listing them in `exclusions/repos.csv`:

1. Create or edit `exclusions/repos.csv`
2. Add one repository name per line
3. The first line can optionally be a header "repository"

Example `exclusions/repos.csv`:
```csv
repository
archived-repo
test-repository
legacy-code
```

Excluded repositories will be automatically skipped during analysis. Note that exclusions take precedence over inclusions - if a repository is both included and excluded, it will be excluded.

### Additional Options
```bash
# Enable debug output (shows excluded repositories)
python src/main.py --pattern "*.tf" --debug

# Limit repository scan
python src/main.py --pattern "*.tf" --limit 5

# Analyze specific branch
python src/main.py --pattern "*.tf" --branch "develop"

# Keep cloned repositories
python src/main.py --pattern "*.tf" --keep-clones
```

### Multiple Pattern Matching
Search for multiple file patterns and content patterns simultaneously:

```bash
# Search for multiple file types
python src/main.py --pattern "*.tf,*.yaml,*.json"

# Search for multiple content patterns in Terraform files
python src/main.py --pattern "*.tf" --contents "required_version,provider \"aws\",resource \"aws"

# Combine multiple file types and content patterns
python src/main.py --pattern "*.tf,*.yaml" --contents "version,apiVersion"
```

The tool will:
1. Search for all specified file patterns
2. For each matching file, search for all specified content patterns
3. Combine all results in the output

## Command Line Arguments

- `--pattern`: Required. Pattern to search for in files (e.g., "*.tf", "src/*.py")
- `--contents`: Optional. Search for specific content within matching files
- `--org`: Optional. Override the GitHub organization name from GITHUB_ORG environment variable
- `--output`: Optional. Output file path (default: reports/results.csv)
- `--format`: Optional. Output format, either 'csv' or 'json' (default: csv)
- `--branch`: Optional. Specific branch to analyze (default: repository default branch)
- `--limit`: Optional. Limit the number of repositories to analyze
- `--debug`: Optional. Show debug information
- `--keep-clones`: Optional. Keep cloned repositories after analysis

## Output Format

### Console Output
The tool provides rich console output showing:
- Files found with matching patterns
- Content matches within files
- Repository statistics
- Total match counts

### CSV Export
The CSV output includes:
- Repository name
- Repository URL
- File path
- Line number (when matches are found)

Example CSV output:
```csv
repository,repository_url,file_path,line_number
main-app,https://github.com/org/main-app,src/config.tf,15
api-service,https://github.com/org/api-service,app/server.py,42
frontend-web,https://github.com/org/frontend-web,src/components/App.js,27
```

When searching for files without content patterns, the line_number field will be empty.

### JSON Export
The JSON output provides detailed information:
- Repository details
- File paths
- Match locations
- Content context
- Line numbers

## Environment Variables

The tool uses the following environment variables from your `.env` file:

- `GITHUB_TOKEN`: Required. Your GitHub Personal Access Token
- `GITHUB_ORG`: Required. Your GitHub organization name (can be overridden with --org)
- `EXCLUSIONS_FILE`: Optional. Path to repository exclusions file (default: exclusions/repos.csv)
- `INCLUSIONS_FILE`: Optional. Path to repository inclusions file (default: inclusions/repos.csv)

## Development

To contribute to the project:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## License

[MIT License](LICENSE)

## Support

For issues and feature requests, please use the GitHub issue tracker. 