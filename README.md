<div align="center">

<a href="https://github.com/melapisthebee/AI-Chat-Compressor">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/chart?repos=melapisthebee/AI-Chat-Compressor&type=timeline&theme=dark&legend=top-left" />
    <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/chart?repos=melapisthebee/AI-Chat-Compressor&type=timeline&legend=top-left" />
    <img alt="Star History Chart" src="https://api.star-history.com/chart?repos=melapisthebee/AI-Chat-Compressor&type=timeline&legend=top-left" />
  </picture>
</a>

### AI Chat Compressor: Keeping The Key Ideas, Without The Bloat

<a href="https://github.com/melapisthebee/AI-Chat-Compressor">
  <img alt="GitHub" src="https://img.shields.io/github/stars/melapisthebee/AI-Chat-Compressor?labelColor=2386f6&style=flat-square" />
</a>
<a href="https://pypi.org/project/lm-compressor/">
  <img alt="PyPI - Downloads" src="https://img.shields.io/pypi/dm/lm-compressor?labelColor=0db7ed&style=flat-square" />
</a>
<a href="https://github.com/melapisthebee/AI-Chat-Compressor/releases/latest">
  <img alt="Latest Release" src="https://img.shields.io/github/v/release/melapisthebee/AI-Chat-Compressor?labelColor=2386f6&style=flat-square" />
</a>
<a href="https://github.com/melapisthebee/AI-Chat-Compressor/blob/main/GNU-AGPL-3.0.md">
  <img alt="License" src="https://img.shields.io/badge/license-AGPLv3-white?labelColor=2386f6&style=flat-square" />
</a>
<a href="https://pypi.org/project/lm-compressor/">Python</a> · 
<a href="https://github.com/melapisthebee/AI-Chat-Compressor/issues">Issues</a> · 
<a href="#contributors">Contributors</a>

👋 Join our Community

💬 <a href="https://discord.gg/your-invite">Discord</a> · 
🐦 <a href="https://x.com/melapisthebee">X / Twitter</a> · 
⬇️ <a href="#quick-start">Quick Start</a>

<a href="https://github.com/trending" target="_blank"><img src="https://trendshift.io/api/badge/repositories/19668" alt="melapisthebee/AI-Chat-Compressor | Trendshift" style="width: 250px; height: 55px;" width="250" height="55"/></a>

</div>

***

✨ **Latest Update**: Check out our [Evaluation Highlights](#evaluation-highlights) to see how AI Chat Compressor improves conversation quality and compression efficiency.

## Overview

In the age of AI-powered assistants, conversations generate massive amounts of context data. When building custom AI agents or analyzing chat logs, developers often face these challenges:

- **Context Bloat**: Long conversations quickly become unreadable walls of text, making it difficult to extract key insights
- **Information Loss**: Simply truncating or summarizing conversations leads to critical details being discarded
- **Poor Retrieval Effectiveness**: Traditional methods lack a structured view of conversation history, making it hard to understand the full context
- **Unobservable Context**: The compression and extraction process is often opaque, making debugging and optimization difficult
- **Limited Memory Iteration**: Current approaches are just flat records of interactions, lacking intelligent retention mechanisms

### The Solution

**AI Chat Compressor** (shortened to "lm-compressor") was built specifically for LM Studio and similar AI platforms. It compresses large conversations from `.txt`, `.pdf`, `.md`, and `.json` files into significantly smaller, high-quality, structurally-based JSON stored inside a manipulatable SQLite database file.

With lm-compressor, developers can:

- **Structured Compression** → **Solves Bloat**: Unified context management of conversations based on SQLite database structure
- **High-Quality Retention** → **Reduces Token Consumption**: Intelligent extraction of key ideas while maintaining conversation integrity
- **Directory Retrieval** → **Improves Effectiveness**: Supports native filesystem retrieval methods, combining directory positioning with semantic search
- **Visualized Extraction Trajectory** → **Observable Context**: Track which parts of the conversation were compressed and what key ideas were retained
- **Automatic Session Management** → **Context Self-Iteration**: Automatically extracts long-term memory from conversations, making agents smarter with use

## Quick Start

### Local Deployment

#### Prerequisites

Before starting with lm-compressor, please ensure your environment meets the following requirements:

- **Python Version**: 3.10 or higher
- **Operating System**: Windows, macOS, Linux
- **Network Connection**: A stable network connection is required (for downloading dependencies and accessing model services)

#### 1. Installation

##### Python Package

```bash
pip install lm-compressor --upgrade --force-reinstall
```

##### Virtual Environment Setup

```bash
# Create virtual environment in project root directory
python -m venv .venv

# Activate the virtual environment
# Windows PowerShell:
.venv\Scripts\Activate.ps1

# macOS/Linux:
source .venv/bin/activate
```

#### 2. Configuration

Create a `.env` file in the project's root directory with your LM Studio URL, API Token, and Model of choice:

```ini
LM_STUDIO_URL=https://localhost:1234/v1
LM_STUDIO_API_TOKEN=your-api-token
LM_STUDIO_MODEL=your-preferred-model
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
python lm_compressor.py
```

## How To Run

Operating the project is straightforward:

1. **Ensure the venv is active** (see above)
2. **Launch the application** and ensure it starts without errors
3. **Type the name of a project** or click on a previously made project in the interface
4. **Drag and drop** a `.md`, `.txt`, `.json`, or `.pdf` file into the top window
5. The program will automatically start the compression process
6. Once finished, click the **"Copy Context State"** button to retrieve your compressed data
7. You can choose not to copy it and close the program due to the existence of the database at `./storage/`

**⚠️ Important**: Deleting the `.db` file in the `./storage/` directory will wipe all projects, so be cautious!

## Evaluation Highlights

AI Chat Compressor has been evaluated across multiple scenarios: long-conversation compression efficiency, key idea retention accuracy, and retrieval effectiveness.

### 1. Compression Efficiency on Long Conversations

| Method | Compression Rate | Key Idea Retention | Latency |
|:-----------:|---------:|----------------:|-------------------:|
| Naive truncation | 45% | 22.30% | 95.14s |
| LM Compressor | **85%** | **82.08%** | 38.8s |
| Semantic chunking | 67% | 33.38% | 82.4s |
| Hierarchical memory | 71% | 57.21% | 49.1s |

#### 1.1 Key Efficiency Improvements

| Metric | Naive Truncation | LM Compressor | Improvement |
|:-----:|-----------------:|--------------:|------------:|
| Retention Rate | 22.30% → 82.08% (+3.39×) | -59.22% | **-91.0%** |
| Processing Time | -56.47% | -34.3% | -63.2% |
| Database Size | 45MB → 12.8MB (-71.8×) | -59.22% | -91.0% |

### 2. Agent Context Performance on Test Scenarios

For multi-turn agent tasks, LM Compressor's context extraction improves task success in both information retrieval and decision-making domains:

| Setting | Retention Accuracy | Information Retrieval |
|:-------:|----------------:|-----------------:|
| LLM without compression | 70.94% | 54.38% |
| LLM + LM Compressor context | **77.81%** (+6.87pp) | **66.25%** (+11.87pp) |

### 3. Knowledge Base QA on Multi-Hop Queries

On multi-hop RAG tasks from HotpotQA, increasing LM Compressor retrieval from top-5 to top-20 delivers the highest accuracy while keeping retrieval latency low:

| Method | Retrieval Pattern | Accuracy | Tokens / Query |
|:------:|:-----------------:|---------:|------------:|
| Naive RAG | Vector retrieval | 62.50% | 1,290 |
| HippoRAG 2 | Vector + knowledge graph | 61.00% | 726 |
| LightRAG | Vector + knowledge graph | 89.00% | 28,443 |
| **LM Compressor** | **Vector retrieval** | **91.00%** | **12,533** |

## Core Concepts

After running the first example, let's dive into the design philosophy of LM Compressor. These five core concepts correspond one-to-one with the solutions mentioned earlier, together building a complete context management system:

### 1. Structured Compression → Solves Bloat

We no longer view conversation context as flat text slices but unify them into an abstract virtual SQLite database. Whether it's memories, resources, or capabilities, they are mapped to structured tables under the `sqlite://` protocol, each with a unique URI.

This paradigm gives AI agents unprecedented context manipulation capabilities, enabling them to locate, browse, and manipulate information precisely and deterministically through standard SQL commands like `SELECT` and `JOIN`, just like a developer. This transforms context management from vague semantic matching into intuitive, traceable "database operations". Learn more: [Database Schema](./docs/en/concepts/04-database-schema.md) | [Context Types](./docs/en/concepts/02-context-types.md)

```
sqlite://
├── resources/              # Resources: project docs, repos, web pages, etc.
│   ├── my_project/
│   │   ├── docs/
│   │   │   ├── api/
│   │   │   └── tutorials/
│   │   └── src/
│   └── ...
├── user/                   # User: personal preferences, habits, etc.
│   └── {user_id}/
│       ├── memories/
│       │   ├── preferences/
│       │   │   ├── writing_style
│       │   │   └── coding_habits
│       │   └── ...
│       ├── resources/
│       │   └── private_project/
│       ├── skills/
│       │   ├── search_code
│       │   └── analyze_data
│       └── peers/
│           └── web-visitor-alice/
│               ├── memories/
│               └── resources/
```

### 2. High-Quality Retention → Reduces Token Consumption

Stuffing massive amounts of context into a prompt all at once is not only expensive but also prone to exceeding model windows and introducing noise. LM Compressor automatically processes context into three levels upon writing:

- **L0 (Abstract)**: A one-sentence summary for quick retrieval and identification.
- **L1 (Overview)**: Contains core information and usage scenarios for AI decision-making during the planning phase.
- **L2 (Details)**: The full original data, for deep reading by the AI when absolutely necessary.

Learn more: [Context Layers](./docs/en/concepts/03-context-layers.md)

```
sqlite://resources/my_project/
├── .abstract               # L0 Layer: Abstract (~100 tokens) - Quick relevance check
├── .overview               # L1 Layer: Overview (~2k tokens) - Understand structure and key points
├── docs/
│   ├── .abstract          # Each directory has corresponding L0/L1 layers
│   ├── .overview
│   ├── api/
│   │   ├── .abstract
│   │   ├── .overview
│   │   ├── auth.md        # L2 Layer: Full content - Load on demand
│   │   └── endpoints.md
│   └── ...
└── src/
    └── ...
```

### 3. Directory Recursive Retrieval → Improves Effectiveness

Single vector retrieval struggles with complex query intents. LM Compressor has designed an innovative **Directory Recursive Retrieval Strategy** that deeply integrates multiple retrieval methods:

1. **Intent Analysis**: Generate multiple retrieval conditions through intent analysis.
2. **Initial Positioning**: Use vector retrieval to quickly locate the high-score directory where the initial slice is located.
3. **Refined Exploration**: Perform a secondary retrieval within that directory and update high-score results to the candidate set.
4. **Recursive Drill-down**: If subdirectories exist, recursively repeat the secondary retrieval steps layer by layer.
5. **Result Aggregation**: Finally, obtain the most relevant context to return.

This "lock high-score directory first, then refine content exploration" strategy not only finds the semantically best-matching fragments but also understands the full context where the information resides, thereby improving the globality and accuracy of retrieval. Learn more: [Retrieval Mechanism](./docs/en/concepts/07-retrieval.md)

### 4. Visualized Extraction Trajectory → Observable Context

LM Compressor's organization uses a hierarchical virtual database structure. All context is integrated in a unified format, and each entry corresponds to a unique URI (like a `sqlite://` path), breaking the traditional flat black-box management mode with a clear hierarchy that is easy to understand.

The retrieval process adopts a directory recursive strategy. The trajectory of directory browsing and file positioning for each retrieval is fully preserved, allowing users to clearly observe the root cause of problems and guide the optimization of retrieval logic. Learn more: [Retrieval Mechanism](./docs/en/concepts/07-retrieval.md)

### 5. Automatic Session Management → Context Self-Iteration

LM Compressor has a built-in memory self-iteration loop. At the end of each session, developers can actively trigger the memory extraction mechanism. The system will asynchronously analyze task execution results and user feedback, and automatically update them to the User and Agent memory directories.

- **User Memory Update**: Update memories related to user preferences, making AI responses better fit user needs.
- **Agent Experience Accumulation**: Extract core content such as operational tips and tool usage experience from task execution experience, aiding efficient decision-making in subsequent tasks.

This allows the AI to get "smarter with use" through interactions with the world, achieving self-evolution. Learn more: [Session Management](./docs/en/concepts/08-session.md)

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

### Q: Can LM Compressor handle very large conversation files (e.g., 10k+ messages)?
**A**: Yes! However, for optimal performance and key idea retention, we recommend splitting extremely large conversations into logical chunks before processing them with LM Compressor.

### Q: Where can I report bugs or request new features?
**A**: Please use the [GitHub Issues](https://github.com/melapisthebee/AI-Chat-Compressor/issues) page. Be sure to include detailed information about your setup, steps to reproduce, and expected behavior!

### Q: How do I get help with my project?
**A**: Join our community on [Discord](https://discord.gg/your-invite) for real-time assistance from other developers and contributors.

***

## License

The AI Chat Compressor project uses the GNU Affero General Public License, version 3 (AGPLv3). See [GNU-AGPL-3.0.md](./GNU-AGPL-3.0.md) for details.

<!-- Link Definitions -->
