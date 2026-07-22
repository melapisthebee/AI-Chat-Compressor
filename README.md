### AI Chat Compressor: Keeping The Key Ideas, Without The Bloat

</div>

***

<div align="center">

<a href="https://github.com/melapisthebee/AI-Chat-Compressor">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/chart?repos=melapisthebee/AI-Chat-Compressor&type=timeline&theme=dark&legend=top-left" />
    <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/chart?repos=melapisthebee/AI-Chat-Compressor&type=timeline&legend=top-left" />
    <img alt="Star History Chart" src="https://api.star-history.com/chart?repos=melapisthebee/AI-Chat-Compressor&type=timeline&legend=top-left" />
  </picture>
</a>

***

## Overview

In the age of AI-powered assistants, conversations generate massive amounts of context data. When building custom AI agents or analyzing chat logs, developers often face these challenges:

- **Context Bloat**: Long conversations quickly become unreadable walls of text, making it difficult to extract key insights
- **Information Loss**: Simply truncating or summarizing conversations leads to critical details being discarded
- **Poor Retrieval Effectiveness**: Traditional methods lack a structured view of conversation history, making it hard to understand the full context
- **Unobservable Context**: The compression and extraction process is often opaque, making debugging and optimization difficult
- **Limited Memory Iteration**: Current approaches are just flat records of interactions, lacking intelligent retention mechanisms

### The Solution

**AI Chat Compressor** (shortened to "lm-compressor") was built specifically to address these issues. It compresses large conversations from `.txt`, `.pdf`, `.md`, and `.json` files into significantly smaller, high-quality, structurally-based JSON stored inside a manipulatable SQLite database file.

With lm-compressor, developers can:

- **Structured Compression** → **Solves Bloat**: Unified context management of conversations based on SQLite database structure
- **High-Quality Retention** → **Reduces Token Consumption**: Intelligent extraction of key ideas while maintaining conversation integrity
- **Directory Retrieval** → **Improves Effectiveness**: Supports native filesystem retrieval methods, combining directory positioning with semantic search
- **Visualized Extraction Trajectory** → **Observable Context**: Track which parts of the conversation were compressed and what key ideas were retained
- **Automatic Session Management** → **Context Self-Iteration**: Automatically extracts long-term memory from conversations, making agents smarter with use

## Quick Start

#### Prerequisites

Before starting with lm-compressor, please ensure your environment meets the following requirements:

- **Python Version**: 3.12 supported. 
- **Operating System**: Windows, macOS, Linux
- **Network Connection**: A stable network connection is required (for downloading dependencies. Afterwards you can go completely offline)

### 1. Installation

#### Install the Python interpeter:

##### Windows
```bash
# Install the latest Python 3 with pip included
winget install Python.Python.3.12

# Verify installation
python --version
```

##### MacOS
```bash
# Install Homebrew if not already installed
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install Python 3 (includes pip)
brew install python

# Verify installation
python3 --version
pip3 --version
```

##### Arch Linux
```bash
# Update package database
sudo pacman -Syu

# Install Python (includes pip as python-pip)
sudo pacman -S python python-pip

# Verify installation
python --version
pip --version
```

##### Fedora Linux
```bash
# Update system
sudo dnf update

# Install Python 3, pip, and development tools
sudo dnf install python3 python3-pip python3-devel

# Verify installation
python3 --version
pip3 --version
```

##### Debain/Ubuntu Linux
```bash
# Update package list
sudo apt update

# Install Python 3, pip, and the python-is-python3 package
sudo apt install python3 python3-pip python-is-python3

# Verify installation
python --version
pip --version
```


##### Virtual Environment Setup

```bash
# Create virtual environment in project root directory
python -m venv .venv

# Activate the virtual environment
# Windows PowerShell:
./.venv/Scripts/activate

# macOS/Linux:
source .venv/bin/activate
```

#### 2. Configuration

Create a `.env` file in the project's root directory with your LM Studio URL, API Token, and Model of choice:

```ini
LM_STUDIO_BASE_URL=https://localhost:1234/v1
LM_STUDIO_API_KEY=your-api-token
DEFAULT_COMPRESSION_MODEL=your-preferred-model
```

#### 3. Environment Validation

```bash
# Verify Python installation
python -m pip --version

# Install dependencies
pip install -r requirements.txt
```

#### 4. Launch

```bash
# Run the application inside the virtual environment
python app.py
```

***

## Contributing

Artificial Intelligence is a powerful tool, but it is not a replacement for human intellect and our ability to create and innovate.

At the end of the day, AI is a complex autocomplete, regardless of its architecture.

Because of this inherent limitation, autocompleted code has to be viewed as flawed and defective until proven otherwise through extensive tests and review.

AI was used to aid in the creation of this program, so AI is allowed to aid in the assistance of adding features and fixing potential/current issues.

If AI is used, you MUST disclose that it has been used so the proper testing can be run on the pull request in question.

**AI is NOT allowed to create issue or pull requests.**

If AI is used to add a feature and/or fix issues,
then you must AT LEAST be able to write in your own words what the added/modified code does and how it aligns with the project's core function.

This is for everyone's benefit. You get to Vibe-Code, so we get to verify.

### Contributors ✨

- **MelapisTheBee** - Core developer and maintainer

***

## FAQ / Support

### Q: What file formats does LM Compressor support?
**A**: Currently, it supports `.txt`, `.pdf`, `.md`, and `.json` files. If you need support for other formats, please open an issue with your use case!

### Q: How do I ensure my compressed data is not lost if the database file gets corrupted?
**A**: Always keep a backup of your `.db` file in a separate location. The compressed data is stored exclusively within this database, so losing it means losing your projects.

### Q: Can LM Compressor handle very large conversation files (e.g., 64k+ messages)?
**A**: Yes! Do note that the larger the conversation, the longer the processing will take. 

### Q: What model is reccomended for this project? 
**A**: I reccomend you use "qwen3-4b-instruct-2507", which you can download from LM Studio. 

### Q: Where can I report bugs or request new features?
**A**: Please use the [GitHub Issues](https://github.com/melapisthebee/AI-Chat-Compressor/issues) page. Be sure to include detailed information about your setup, steps to reproduce, and expected behavior!


## License

The AI Chat Compressor project uses the GNU Affero General Public License, version 3 (AGPLv3). See [GNU-AGPL-3.0.md](./GNU-AGPL-3.0.md) for details.

<!-- Link Definitions -->
